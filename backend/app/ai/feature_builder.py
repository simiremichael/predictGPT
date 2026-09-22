"""AI feature builder.

Converts research evidence into structured prediction features that the
AI adjustment layer can consume. Features are boolean/continuous flags
representing the impact of web evidence on the match prediction.

This module does NOT directly assign score probabilities. It only
characterizes what evidence was found and how it might affect attack/defense.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from web_research.schemas import (
    EvidenceStatus,
    InjuryEvidence,
    LineupEvidence,
    LineupStatus,
    MatchResearchResult,
    SuspensionEvidence,
    TeamNewsEvidence,
)

from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class AIFeatureVector:
    """Structured features derived from AI research evidence."""

    key_attacker_missing: bool = False
    key_defender_missing: bool = False
    starting_goalkeeper_missing: bool = False
    multiple_defenders_missing: bool = False
    important_midfielder_missing: bool = False
    recent_manager_change: bool = False
    expected_lineup_stability: float = 1.0
    rotation_risk: bool = False
    fixture_congestion: bool = False
    tactical_change: bool = False
    evidence_summary: str = ""
    evidence_text: str = ""
    source_count: int = 0
    average_credibility: float = 0.0
    average_freshness: float = 0.0
    injuries: list[dict[str, Any]] = field(default_factory=list)
    suspensions: list[dict[str, Any]] = field(default_factory=list)
    lineups: list[dict[str, Any]] = field(default_factory=list)
    team_news: list[dict[str, Any]] = field(default_factory=list)
    research_available: bool = False
    data_quality: float = 0.0
    research_run_id: str | None = None


class AIFeatureBuilder:
    """Converts research evidence into AI features for prediction adjustment."""

    KEY_ATTACKER_ROLES = {"forward", "attacker", "striker", "winger"}
    KEY_DEFENDER_ROLES = {
        "centre_back", "centre-back", "cb", "full_back", "full-back",
        "lb", "rb", "defender", "goalkeeper", "gk",
    }
    MIDFIELDER_ROLES = {
        "midfielder", "midfield", "cm", "cam", "cdm", "lm", "rm",
    }

    def build(self, research_result: MatchResearchResult | None) -> AIFeatureVector:
        """Build AI features from a research result.

        If research_result is None, returns an empty AIFeatureVector with
        research_available=False.
        """
        if research_result is None:
            return AIFeatureVector(research_available=False)

        vector = AIFeatureVector(
            research_available=True,
            data_quality=research_result.data_quality,
            research_run_id=research_result.research_run_id,
            source_count=len(research_result.sources),
            average_credibility=self._avg_credibility(research_result.sources),
            average_freshness=self._avg_freshness(research_result.sources),
        )

        self._process_injuries(research_result.injuries, vector)
        self._process_suspensions(research_result.suspensions, vector)
        self._process_lineups(research_result.lineups, vector)
        self._process_team_news(research_result.team_news, vector)

        vector.evidence_text = self._build_evidence_text(research_result, vector)
        vector.evidence_summary = self._build_evidence_summary(vector)

        return vector

    def _process_injuries(
        self, injuries: list[InjuryEvidence], vector: AIFeatureVector
    ) -> None:
        """Process injury evidence into features."""
        for injury in injuries:
            if injury.evidence_status in (
                EvidenceStatus.CONFIRMED,
                EvidenceStatus.REPORTED,
                EvidenceStatus.PROBABLE,
            ):
                vector.injuries.append(injury.model_dump())

                position_lower = (injury.position or "").lower().replace(" ", "_")
                if any(role in position_lower for role in {"forward", "attacker", "striker", "winger"}):
                    vector.key_attacker_missing = True
                elif any(
                    role in position_lower
                    for role in {"defender", "centre_back", "centre-back", "cb", "full_back", "lb", "rb", "gk", "goalkeeper"}
                ):
                    if "goalkeeper" in position_lower or position_lower in {"gk"}:
                        vector.starting_goalkeeper_missing = True
                    else:
                        vector.key_defender_missing = True
                elif any(
                    role in position_lower
                    for role in {"midfielder", "midfield", "cm", "cam", "cdm", "lm", "rm"}
                ):
                    vector.important_midfielder_missing = True

        defender_missing_count = sum(
            1 for i in vector.injuries
            if any(
                role in (i.get("position") or "").lower().replace(" ", "_")
                for role in {"defender", "centre_back", "centre-back", "cb", "full_back", "lb", "rb"}
            )
        )
        if defender_missing_count >= 2:
            vector.multiple_defenders_missing = True

    def _process_suspensions(
        self, suspensions: list[SuspensionEvidence], vector: AIFeatureVector
    ) -> None:
        """Process suspension evidence into features."""
        for susp in suspensions:
            if susp.evidence_status in (EvidenceStatus.CONFIRMED, EvidenceStatus.REPORTED):
                vector.suspensions.append(susp.model_dump())

                position_lower = (susp.position or "").lower()
                if any(role in position_lower for role in self.KEY_ATTACKER_ROLES):
                    vector.key_attacker_missing = True
                elif any(role in position_lower for role in self.KEY_DEFENDER_ROLES):
                    vector.key_defender_missing = True

    def _process_lineups(
        self, lineups: list[LineupEvidence], vector: AIFeatureVector
    ) -> None:
        """Process lineup evidence into features."""
        for lineup in lineups:
            vector.lineups.append(lineup.model_dump())

            if lineup.status == LineupStatus.CONFIRMED:
                vector.expected_lineup_stability = 1.0
            elif lineup.status == LineupStatus.PREDICTED:
                vector.expected_lineup_stability = max(
                    0.5, vector.expected_lineup_stability
                )
                vector.rotation_risk = True

    def _process_team_news(
        self, team_news: list[TeamNewsEvidence], vector: AIFeatureVector
    ) -> None:
        """Process team news evidence into features."""
        for news in team_news:
            vector.team_news.append(news.model_dump())

            if news.news_type == "manager_change":
                vector.recent_manager_change = True
            elif news.news_type == "tactical_change":
                vector.tactical_change = True
            elif news.news_type == "rotation":
                vector.rotation_risk = True
            elif news.news_type == "fixture_congestion":
                vector.fixture_congestion = True

    def _build_evidence_text(
        self, research_result: MatchResearchResult, vector: AIFeatureVector
    ) -> str:
        """Build a text summary of evidence for AI prompts."""
        parts: list[str] = []

        for injury in vector.injuries:
            parts.append(
                f"Injury: {injury.get('player')} - team="
                f"{injury.get('team')}, status={injury.get('status')}, "
                f"evidence={injury.get('evidence_status')}, "
                f"confidence={injury.get('confidence')}"
            )

        for susp in vector.suspensions:
            parts.append(
                f"Suspension: {susp.get('player')} - team={susp.get('team')}, "
                f"status={susp.get('suspension_status')}, "
                f"evidence={susp.get('evidence_status')}"
            )

        for lineup in vector.lineups:
            parts.append(
                f"Lineup: team={lineup.get('team')}, status={lineup.get('status')}, "
                f"confidence={lineup.get('confidence')}"
            )

        for news in vector.team_news:
            parts.append(
                f"News: team={news.get('team')}, type={news.get('news_type')}, "
                f"evidence={news.get('evidence_status')}, summary={news.get('summary')}"
            )

        return "\n".join(parts) if parts else "No evidence found."

    def _build_evidence_summary(self, vector: AIFeatureVector) -> str:
        """Build a concise human-readable evidence summary."""
        parts: list[str] = []

        if vector.injuries:
            parts.append(f"{len(vector.injuries)} injury records")
        if vector.suspensions:
            parts.append(f"{len(vector.suspensions)} suspension records")
        if vector.lineups:
            parts.append(f"{len(vector.lineups)} lineup records")
        if vector.team_news:
            parts.append(f"{len(vector.team_news)} news items")
        parts.append(f"{vector.source_count} sources")

        return "; ".join(parts) if parts else "No evidence"

    @staticmethod
    def _avg_credibility(sources: list[Any]) -> float:
        if not sources:
            return 0.0
        return sum(getattr(s, "credibility_score", 0) for s in sources) / len(sources)

    @staticmethod
    def _avg_freshness(sources: list[Any]) -> float:
        if not sources:
            return 0.0
        return sum(getattr(s, "freshness_score", 0) for s in sources) / len(sources)

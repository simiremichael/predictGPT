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
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from prediction.features import FeatureVector

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
    search_context: list[dict[str, Any]] = field(default_factory=list)
    research_available: bool = False
    data_quality: float = 0.0
    research_run_id: str | None = None
    # Statistical context for AI adjustment layer
    h2h_record: dict[str, Any] | None = None
    home_league_position: int | None = None
    away_league_position: int | None = None
    home_standing_points_per_game: float | None = None
    away_standing_points_per_game: float | None = None
    home_avg_goals_per_game: float | None = None
    away_avg_goals_per_game: float | None = None
    h2h_avg_goals_per_game: float | None = None
    league_position_advantage: int | None = None
    standing_ppg_advantage: float | None = None
    avg_goals_advantage: float | None = None
    # Recent goal statistics for BTTS / over-under differentiation
    home_btts_rate: float | None = None
    away_btts_rate: float | None = None
    home_over_2_5_rate: float | None = None
    away_over_2_5_rate: float | None = None
    home_avg_total_goals: float | None = None
    away_avg_total_goals: float | None = None


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

    def build(
        self,
        research_result: MatchResearchResult | None,
        match_input: Any = None,
        features: FeatureVector | None = None,
    ) -> AIFeatureVector:
        """Build AI features from a research result.

        If research_result is None, returns an empty AIFeatureVector with
        research_available=False. If match_input is provided, statistical
        context (H2H, league positions, average goals) is included.
        If features (computed FeatureVector) is provided, BTTS/over-under
        and other derived statistics are included.
        """
        if research_result is None:
            vector = AIFeatureVector(research_available=False)
        else:
            vector = AIFeatureVector(
                research_available=True,
                data_quality=research_result.data_quality,
                research_run_id=research_result.research_run_id,
                source_count=len(research_result.sources),
                average_credibility=self._avg_credibility(research_result.sources),
                average_freshness=self._avg_freshness(research_result.sources),
            )

        if match_input is not None:
            self._populate_match_context(match_input, vector, features)

        if research_result is not None:
            self._process_injuries(research_result.injuries, vector)
            self._process_suspensions(research_result.suspensions, vector)
            self._process_lineups(research_result.lineups, vector)
            self._process_team_news(research_result.team_news, vector)
            vector.search_context = self._build_search_context(research_result.sources)

        vector.evidence_text = self._build_evidence_text(research_result, vector)
        vector.evidence_summary = self._build_evidence_summary(vector)

        return vector

    def _populate_match_context(
        self,
        match_input: Any,
        vector: AIFeatureVector,
        features: FeatureVector | None = None,
    ) -> None:
        """Extract statistical context from match input and attach to vector."""
        h2h = getattr(match_input, "h2h", None)

        if h2h:
            vector.h2h_record = h2h.model_dump()
            vector.h2h_avg_goals_per_game = getattr(h2h, "avg_goals_per_game", None)

        home_stats = getattr(match_input, "home_team_stats", None)
        away_stats = getattr(match_input, "away_team_stats", None)

        if home_stats:
            vector.home_league_position = getattr(home_stats, "position", None)
            vector.home_standing_points_per_game = getattr(home_stats, "points_per_game", None)
            vector.home_avg_goals_per_game = getattr(home_stats, "goals_per_game", None)

        if away_stats:
            vector.away_league_position = getattr(away_stats, "position", None)
            vector.away_standing_points_per_game = getattr(away_stats, "points_per_game", None)
            vector.away_avg_goals_per_game = getattr(away_stats, "goals_per_game", None)

        if vector.home_league_position is not None and vector.away_league_position is not None:
            vector.league_position_advantage = (
                vector.away_league_position - vector.home_league_position
            )

        if (
            vector.home_standing_points_per_game is not None
            and vector.away_standing_points_per_game is not None
        ):
            vector.standing_ppg_advantage = (
                vector.home_standing_points_per_game
                - vector.away_standing_points_per_game
            )

        if (
            vector.home_avg_goals_per_game is not None
            and vector.away_avg_goals_per_game is not None
        ):
            vector.avg_goals_advantage = (
                vector.home_avg_goals_per_game - vector.away_avg_goals_per_game
            )

        # Populate BTTS / over-under statistics from computed FeatureVector
        if features is not None:
            vector.home_btts_rate = features.home_btts_rate
            vector.away_btts_rate = features.away_btts_rate
            vector.home_over_2_5_rate = features.home_over_2_5_rate
            vector.away_over_2_5_rate = features.away_over_2_5_rate
            vector.home_avg_total_goals = features.home_avg_total_goals
            vector.away_avg_total_goals = features.away_avg_total_goals

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
        self, research_result: MatchResearchResult | None, vector: AIFeatureVector
    ) -> str:
        """Build a text summary of evidence for AI prompts."""
        parts: list[str] = []

        # Statistical context from match input
        if vector.h2h_avg_goals_per_game is not None:
            parts.append(
                f"H2H average goals per game: {vector.h2h_avg_goals_per_game:.2f}"
            )
        if vector.home_avg_goals_per_game is not None and vector.away_avg_goals_per_game is not None:
            parts.append(
                f"Home team goals per game: {vector.home_avg_goals_per_game:.2f}, "
                f"Away team goals per game: {vector.away_avg_goals_per_game:.2f}"
            )
        if vector.home_league_position is not None and vector.away_league_position is not None:
            parts.append(
                f"Home league position: {vector.home_league_position}, "
                f"Away league position: {vector.away_league_position}"
            )
        if vector.home_standing_points_per_game is not None and vector.away_standing_points_per_game is not None:
            parts.append(
                f"Home points per game: {vector.home_standing_points_per_game:.2f}, "
                f"Away points per game: {vector.away_standing_points_per_game:.2f}"
            )
        if vector.league_position_advantage is not None:
            parts.append(
                f"League position advantage for home team: {vector.league_position_advantage} places"
            )
        if vector.avg_goals_advantage is not None:
            parts.append(
                f"Goals per game advantage for home team: {vector.avg_goals_advantage:.2f}"
            )

        # BTTS / over-under context for market differentiation
        if vector.home_btts_rate is not None and vector.away_btts_rate is not None:
            parts.append(
                f"Home BTTS rate: {vector.home_btts_rate:.2f}, "
                f"Away BTTS rate: {vector.away_btts_rate:.2f}"
            )
        if vector.home_over_2_5_rate is not None and vector.away_over_2_5_rate is not None:
            parts.append(
                f"Home over 2.5 rate: {vector.home_over_2_5_rate:.2f}, "
                f"Away over 2.5 rate: {vector.away_over_2_5_rate:.2f}"
            )
        if vector.home_avg_total_goals is not None and vector.away_avg_total_goals is not None:
            parts.append(
                f"Home avg total goals: {vector.home_avg_total_goals:.2f}, "
                f"Away avg total goals: {vector.away_avg_total_goals:.2f}"
            )

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

        for item in vector.search_context:
            parts.append(
                "Unverified DuckDuckGo search material "
                f"(category={item['category']}, credibility={item['credibility']}, "
                f"source={item['url']}): "
                f"{item['text']}"
            )

        return "\n".join(parts) if parts else ""

    @staticmethod
    def _build_search_context(sources: list[Any]) -> list[dict[str, Any]]:
        """Keep concise, attributable snippets for statistical search topics."""
        relevant_categories = {
            "recent_form",
            "historical_scores",
            "away_historical_scores",
            "league_standings",
            "head_to_head",
            "season_team_statistics",
            "fixture_congestion",
            "market_odds",
            "match_conditions",
        }
        relevant_sources = sorted(
            (
                source for source in sources
                if relevant_categories.intersection(
                    set(getattr(source, "search_categories", []) or [])
                    | ({getattr(source, "search_category", None)}
                       if getattr(source, "search_category", None) else set())
                )
                and (getattr(source, "snippet", None) or getattr(source, "content", None))
            ),
            key=lambda source: (
                getattr(source, "credibility_score", 0.0),
                getattr(source, "freshness_score", 0.0),
            ),
            reverse=True,
        )
        context: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        for source in relevant_sources:
            url = getattr(source, "url", "")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            categories = set(getattr(source, "search_categories", []) or [])
            if getattr(source, "search_category", None):
                categories.add(source.search_category)
            category = sorted(categories.intersection(relevant_categories))[0]
            text = " ".join(
                (getattr(source, "snippet", None) or getattr(source, "content", None) or "").split()
            )
            if not text:
                continue
            title = getattr(source, "title", None)
            if title:
                text = f"{title}. {text}"
            context.append({
                "category": category,
                "url": url,
                "credibility": getattr(source, "credibility_score", 0.0),
                "text": text[:500],
            })
            if len(context) >= 12:
                break
        return context

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

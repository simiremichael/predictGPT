"""Pydantic schemas for web research data structures."""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class SourceType(StrEnum):
    """Classification of source reliability levels."""

    OFFICIAL_TEAM = "official_team"
    OFFICIAL_LEAGUE = "official_league"
    OFFICIAL_COMPETITION = "official_competition"
    REPUTABLE_NEWS = "reputable_news"
    SPORTS_MEDIA = "sports_media"
    JOURNALIST = "journalist"
    SEARCH_RESULT = "search_result"
    SOCIAL_MEDIA = "social_media"
    BLOG = "blog"
    UNKNOWN = "unknown"


class ResearchSource(BaseModel):
    """A single normalized research source (web page, article, etc.)."""

    url: str
    title: str | None = None
    publisher: str | None = None
    published_at: datetime | None = None
    retrieved_at: datetime = Field(default_factory=datetime.utcnow)
    source_type: SourceType = SourceType.UNKNOWN
    snippet: str | None = None
    content: str | None = None
    credibility_score: float = 0.5
    freshness_score: float = 0.5
    content_source: str = "search_result_snippet"
    relevance: float | None = None


class EvidenceStatus(StrEnum):
    """Confidence level of an extracted claim."""

    CONFIRMED = "confirmed"
    REPORTED = "reported"
    PROBABLE = "probable"
    SPECULATIVE = "speculative"
    UNKNOWN = "unknown"


class InjuryEvidence(BaseModel):
    """Structured injury evidence extracted from web sources."""

    player: str
    team: str | None = None
    position: str | None = None
    status: str | None = None
    injury_type: str | None = None
    expected_return: str | None = None
    evidence_status: EvidenceStatus = EvidenceStatus.UNKNOWN
    confidence: float = 0.0
    source_ids: list[str] = Field(default_factory=list)


class SuspensionEvidence(BaseModel):
    """Structured suspension evidence extracted from web sources."""

    player: str
    team: str | None = None
    position: str | None = None
    competition: str | None = None
    suspension_status: str | None = None
    matches_remaining: int | None = None
    return_date: str | None = None
    evidence_status: EvidenceStatus = EvidenceStatus.UNKNOWN
    confidence: float = 0.0
    source_ids: list[str] = Field(default_factory=list)


class LineupStatus(StrEnum):
    """Status of an extracted lineup."""

    CONFIRMED = "confirmed"
    PREDICTED = "predicted"
    PROBABLE = "probable"
    UNKNOWN = "unknown"


class NormalizedLineupPlayer(BaseModel):
    name: str
    position: str | None = None
    jersey_number: int | None = None
    is_starting: bool = True


class LineupEvidence(BaseModel):
    """Structured lineup evidence extracted from web sources."""

    team: str
    status: LineupStatus = LineupStatus.UNKNOWN
    formation: str | None = None
    goalkeeper: NormalizedLineupPlayer | None = None
    defenders: list[NormalizedLineupPlayer] = Field(default_factory=list)
    midfielders: list[NormalizedLineupPlayer] = Field(default_factory=list)
    attackers: list[NormalizedLineupPlayer] = Field(default_factory=list)
    bench: list[NormalizedLineupPlayer] = Field(default_factory=list)
    unavailable_players: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    evidence_status: EvidenceStatus = EvidenceStatus.UNKNOWN
    source_ids: list[str] = Field(default_factory=list)


class TeamNewsEvidence(BaseModel):
    """Structured team news evidence extracted from web sources."""

    team: str
    news_type: str
    summary: str | None = None
    affected_players: list[str] = Field(default_factory=list)
    tactical_effect: str | None = None
    importance: str = "medium"
    evidence_status: EvidenceStatus = EvidenceStatus.UNKNOWN
    confidence: float = 0.0
    source_ids: list[str] = Field(default_factory=list)


class EvidenceConflict(BaseModel):
    """Representation of conflicting evidence from different sources."""

    subject: str
    claim_a: str
    claim_b: str
    source_a_id: str
    source_b_id: str
    detected_at: datetime = Field(default_factory=datetime.utcnow)


class MatchResearchResult(BaseModel):
    """Complete research result for a single match."""

    match_id: str
    researched_at: datetime = Field(default_factory=datetime.utcnow)
    sources: list[ResearchSource] = Field(default_factory=list)
    injuries: list[InjuryEvidence] = Field(default_factory=list)
    suspensions: list[SuspensionEvidence] = Field(default_factory=list)
    lineups: list[LineupEvidence] = Field(default_factory=list)
    team_news: list[TeamNewsEvidence] = Field(default_factory=list)
    conflicts: list[EvidenceConflict] = Field(default_factory=list)
    data_quality: float = 0.0
    research_run_id: str | None = None


class AIFeatureAdjustment(BaseModel):
    """Bounded AI adjustment to prediction features."""

    home_attack_adjustment: float = 0.0
    away_attack_adjustment: float = 0.0
    home_defense_adjustment: float = 0.0
    away_defense_adjustment: float = 0.0
    confidence: float = 0.0
    reason_codes: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)

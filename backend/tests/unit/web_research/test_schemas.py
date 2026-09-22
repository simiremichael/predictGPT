"""Tests for web research schemas and data structures."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import BaseModel

from web_research.schemas import (
    AIFeatureAdjustment,
    EvidenceConflict,
    EvidenceStatus,
    InjuryEvidence,
    LineupEvidence,
    LineupStatus,
    MatchResearchResult,
    ResearchSource,
    SourceType,
    SuspensionEvidence,
    TeamNewsEvidence,
)


class TestSourceType:
    def test_source_type_values(self) -> None:
        assert SourceType.OFFICIAL_TEAM == "official_team"
        assert SourceType.REPUTABLE_NEWS == "reputable_news"
        assert SourceType.UNKNOWN == "unknown"


class TestEvidenceStatus:
    def test_evidence_status_values(self) -> None:
        assert EvidenceStatus.CONFIRMED == "confirmed"
        assert EvidenceStatus.REPORTED == "reported"
        assert EvidenceStatus.SPECULATIVE == "speculative"
        assert EvidenceStatus.UNKNOWN == "unknown"


class TestLineupStatus:
    def test_lineup_status_values(self) -> None:
        assert LineupStatus.CONFIRMED == "confirmed"
        assert LineupStatus.PREDICTED == "predicted"
        assert LineupStatus.UNKNOWN == "unknown"


class TestResearchSource:
    def test_required_fields(self) -> None:
        source = ResearchSource(
            url="https://example.com",
            title="Test",
            publisher="Test Publisher",
            credibility_score=0.8,
            freshness_score=0.9,
        )
        assert source.url == "https://example.com"
        assert source.credibility_score == 0.8
        assert source.content_source == "search_result_snippet"

    def test_defaults(self) -> None:
        source = ResearchSource(url="https://example.com")
        assert source.relevance is None
        assert source.credibility_score == 0.5
        assert source.freshness_score == 0.5


class TestInjuryEvidence:
    def test_required_fields(self) -> None:
        injury = InjuryEvidence(
            player="John Doe",
        )
        assert injury.player == "John Doe"
        assert injury.evidence_status == EvidenceStatus.UNKNOWN

    def test_with_all_fields(self) -> None:
        injury = InjuryEvidence(
            player="John Doe",
            team="Arsenal",
            status="doubtful",
            injury_type="hamstring",
            expected_return="2024-01-15",
            evidence_status=EvidenceStatus.REPORTED,
            confidence=0.8,
            source_ids=["src1", "src2"],
        )
        assert injury.player == "John Doe"
        assert injury.team == "Arsenal"
        assert injury.confidence == 0.8
        assert len(injury.source_ids) == 2


class TestSuspensionEvidence:
    def test_defaults(self) -> None:
        susp = SuspensionEvidence(player="John Doe")
        assert susp.player == "John Doe"
        assert susp.evidence_status == EvidenceStatus.UNKNOWN
        assert susp.confidence == 0.0


class TestLineupEvidence:
    def test_defaults(self) -> None:
        lineup = LineupEvidence(team="Arsenal")
        assert lineup.team == "Arsenal"
        assert lineup.status == LineupStatus.UNKNOWN


class TestTeamNewsEvidence:
    def test_news_type_required(self) -> None:
        news = TeamNewsEvidence(team="Arsenal", news_type="tactical_change")
        assert news.team == "Arsenal"
        assert news.news_type == "tactical_change"


class TestEvidenceConflict:
    def test_required_fields(self) -> None:
        conflict = EvidenceConflict(
            subject="player_availability",
            claim_a="Player will start",
            claim_b="Player will miss match",
            source_a_id="src1",
            source_b_id="src2",
        )
        assert conflict.subject == "player_availability"


class TestMatchResearchResult:
    def test_defaults(self) -> None:
        result = MatchResearchResult(match_id="match1")
        assert result.match_id == "match1"
        assert len(result.sources) == 0
        assert len(result.injuries) == 0
        assert result.data_quality == 0.0


class TestAIFeatureAdjustment:
    def test_defaults(self) -> None:
        adj = AIFeatureAdjustment()
        assert adj.home_attack_adjustment == 0.0
        assert adj.away_attack_adjustment == 0.0
        assert adj.home_defense_adjustment == 0.0
        assert adj.away_defense_adjustment == 0.0
        assert adj.confidence == 0.0

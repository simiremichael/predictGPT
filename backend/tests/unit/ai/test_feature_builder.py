"""Tests for the AI feature builder."""
from __future__ import annotations

from datetime import datetime

import pytest
from web_research.schemas import (
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

from ai.feature_builder import AIFeatureBuilder


@pytest.fixture
def research_result() -> MatchResearchResult:
    return MatchResearchResult(
        match_id="test-match",
        sources=[
            ResearchSource(
                url="https://example.com/news",
                title="Test News",
                publisher="BBC",
                source_type=SourceType.REPUTABLE_NEWS,
                credibility_score=0.9,
                freshness_score=0.8,
            )
        ],
        injuries=[
            InjuryEvidence(
                player="Test Player",
                team="Home Team",
                position="forward",
                status="doubtful",
                injury_type="hamstring",
                evidence_status=EvidenceStatus.REPORTED,
                confidence=0.8,
                source_ids=["src1"],
            )
        ],
        suspensions=[],
        lineups=[],
        team_news=[],
        conflicts=[],
        data_quality=0.75,
    )


class TestAIFeatureBuilder:
    def test_build_with_none_returns_empty(self) -> None:
        builder = AIFeatureBuilder()
        features = builder.build(None)
        assert features.research_available is False
        assert features.evidence_text == ""

    def test_build_with_research_result(self, research_result: MatchResearchResult) -> None:
        builder = AIFeatureBuilder()
        features = builder.build(research_result)

        assert features.research_available is True
        assert features.data_quality == 0.75
        assert features.source_count == 1
        assert len(features.injuries) == 1
        assert len(features.evidence_text) > 0

    def test_key_attacker_missing_detected(self) -> None:
        builder = AIFeatureBuilder()
        result = MatchResearchResult(
            match_id="test",
            injuries=[
                InjuryEvidence(
                    player="Star Forward",
                    team="Home",
                    position="forward",
                    status="doubtful",
                    evidence_status=EvidenceStatus.REPORTED,
                    confidence=0.8,
                    source_ids=["s1"],
                )
            ],
        )
        features = builder.build(result)
        assert features.key_attacker_missing is True

    def test_key_defender_missing_detected(self) -> None:
        builder = AIFeatureBuilder()
        result = MatchResearchResult(
            match_id="test",
            injuries=[
                InjuryEvidence(
                    player="Center Back",
                    team="Away",
                    position="centre back",
                    status="doubtful",
                    evidence_status=EvidenceStatus.CONFIRMED,
                    confidence=0.9,
                    source_ids=["s1"],
                )
            ],
        )
        features = builder.build(result)
        assert features.key_defender_missing is True

    def test_multiple_defenders_missing(self) -> None:
        builder = AIFeatureBuilder()
        result = MatchResearchResult(
            match_id="test",
            injuries=[
                InjuryEvidence(
                    player="Defender 1",
                    team="Home",
                    position="centre back",
                    status="doubtful",
                    evidence_status=EvidenceStatus.REPORTED,
                    confidence=0.8,
                    source_ids=["s1"],
                ),
                InjuryEvidence(
                    player="Defender 2",
                    team="Home",
                    position="cb",
                    status="doubtful",
                    evidence_status=EvidenceStatus.REPORTED,
                    confidence=0.8,
                    source_ids=["s2"],
                ),
            ],
        )
        features = builder.build(result)
        assert features.multiple_defenders_missing is True

    def test_speculative_evidence_ignored(self) -> None:
        builder = AIFeatureBuilder()
        result = MatchResearchResult(
            match_id="test",
            injuries=[
                InjuryEvidence(
                    player="Player",
                    team="Home",
                    position="forward",
                    status="doubtful",
                    evidence_status=EvidenceStatus.SPECULATIVE,
                    confidence=0.3,
                    source_ids=["s1"],
                )
            ],
        )
        features = builder.build(result)
        assert features.key_attacker_missing is False

    def test_team_news_processing(self) -> None:
        builder = AIFeatureBuilder()
        result = MatchResearchResult(
            match_id="test",
            team_news=[
                TeamNewsEvidence(
                    team="Home",
                    news_type="manager_change",
                    summary="Manager sacked",
                    evidence_status=EvidenceStatus.REPORTED,
                    confidence=0.7,
                    source_ids=["s1"],
                )
            ],
        )
        features = builder.build(result)
        assert features.recent_manager_change is True

    def test_lineup_confirmed(self) -> None:
        builder = AIFeatureBuilder()
        result = MatchResearchResult(
            match_id="test",
            lineups=[
                LineupEvidence(
                    team="Home",
                    status=LineupStatus.CONFIRMED,
                    confidence=0.9,
                    evidence_status=EvidenceStatus.CONFIRMED,
                    source_ids=["s1"],
                )
            ],
        )
        features = builder.build(result)
        assert features.expected_lineup_stability == 1.0

    def test_evidence_summary_text(self, research_result: MatchResearchResult) -> None:
        builder = AIFeatureBuilder()
        features = builder.build(research_result)
        assert "injury records" in features.evidence_summary or "sources" in features.evidence_summary

"""Provider independence tests.

Verifies that the prediction engine produces identical output when given
identical normalized data, regardless of whether the data came from
API-Football or Sportmonks.

This proves the prediction engine is completely provider-independent.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import pytest

from football_data.models import (
    NormalizedFixture,
    NormalizedTeamStatistics,
)
from prediction.base import PredictionInput
from prediction.features import FeatureBuilder, LeagueBaseline
from prediction.poisson import PoissonModel


@pytest.fixture
def league_baseline() -> LeagueBaseline:
    return LeagueBaseline(
        league_id="premier_league",
        avg_home_goals=1.5,
        avg_away_goals=1.0,
        avg_total_goals=2.5,
        home_win_rate=0.45,
        draw_rate=0.27,
        away_win_rate=0.28,
        btts_rate=0.52,
        over_2_5_rate=0.48,
        games_played=380,
    )


class TestProviderIndependence:
    """Tests that the prediction engine is provider-independent."""

    def test_identical_stats_produce_identical_lambdas(
        self, league_baseline: LeagueBaseline
    ) -> None:
        """Two matches with identical normalized stats should produce identical lambdas."""
        home_stats = NormalizedTeamStatistics(
            provider="api_football",
            provider_team_id="123",
            league_id="premier_league",
            season_id="2023",
            is_home=True,
            games_played=20,
            goals_for=35,
            goals_against=20,
            goals_per_game=1.75,
            goals_conceded_per_game=1.0,
            average_xg=1.75,
            average_xga=1.0,
        )
        away_stats = NormalizedTeamStatistics(
            provider="api_football",
            provider_team_id="456",
            league_id="premier_league",
            season_id="2023",
            is_home=False,
            games_played=20,
            goals_for=24,
            goals_against=28,
            goals_per_game=1.2,
            goals_conceded_per_game=1.4,
            average_xg=1.2,
            average_xga=1.4,
        )

        # Create two identical matches with different provider names
        match_api_football = PredictionInput(
            match_id="match-af-1",
            home_team_id="h1",
            away_team_id="a1",
            home_team_name="Home FC",
            away_team_name="Away FC",
            league_id="premier_league",
            kickoff_at=datetime.utcnow() + timedelta(days=1),
            home_team_stats=home_stats,
            away_team_stats=away_stats,
            provider="api_football",
        )

        # Same stats but "sportmonks" provider
        home_stats_sm = NormalizedTeamStatistics(
            provider="sportmonks",
            provider_team_id="789",
            league_id="premier_league",
            season_id="2023",
            is_home=True,
            games_played=20,
            goals_for=35,
            goals_against=20,
            goals_per_game=1.75,
            goals_conceded_per_game=1.0,
            average_xg=1.75,
            average_xga=1.0,
        )
        away_stats_sm = NormalizedTeamStatistics(
            provider="sportmonks",
            provider_team_id="012",
            league_id="premier_league",
            season_id="2023",
            is_home=False,
            games_played=20,
            goals_for=24,
            goals_against=28,
            goals_per_game=1.2,
            goals_conceded_per_game=1.4,
            average_xg=1.2,
            average_xga=1.4,
        )

        match_sportmonks = PredictionInput(
            match_id="match-sm-1",
            home_team_id="h1",
            away_team_id="a1",
            home_team_name="Home FC",
            away_team_name="Away FC",
            league_id="premier_league",
            kickoff_at=datetime.utcnow() + timedelta(days=1),
            home_team_stats=home_stats_sm,
            away_team_stats=away_stats_sm,
            provider="sportmonks",
        )

        model = PoissonModel()
        result_af = model.predict(match_api_football)
        result_sm = model.predict(match_sportmonks)

        # Lambdas should be identical
        assert result_af.lambda_home == pytest.approx(result_sm.lambda_home, abs=1e-6)
        assert result_af.lambda_away == pytest.approx(result_sm.lambda_away, abs=1e-6)

        # Score matrices should be identical
        assert result_af.home_goal_distribution == pytest.approx(
            result_sm.home_goal_distribution, abs=1e-6
        )
        assert result_af.away_goal_distribution == pytest.approx(
            result_sm.away_goal_distribution, abs=1e-6
        )

        # Feature snapshots should be identical (provider-agnostic parts)
        assert result_af.feature_snapshot["home_attack_strength"] == pytest.approx(
            result_sm.feature_snapshot["home_attack_strength"], abs=1e-6
        )

    def test_feature_builder_is_provider_independent(
        self, league_baseline: LeagueBaseline
    ) -> None:
        """FeatureBuilder should produce same strengths regardless of provider label."""
        stats = NormalizedTeamStatistics(
            provider="api_football",
            provider_team_id="1",
            league_id="test",
            games_played=10,
            goals_for=20,
            goals_against=10,
            goals_per_game=2.0,
            goals_conceded_per_game=1.0,
        )

        match = PredictionInput(
            match_id="m1",
            home_team_id="h",
            away_team_id="a",
            home_team_name="H",
            away_team_name="A",
            league_id="test",
            home_team_stats=stats,
            provider="sportmonks",  # Note: provider is sportmonks
        )

        builder = FeatureBuilder()
        features = builder.build(match, league_baseline=league_baseline)

        # Provider label should not affect strength calculation
        assert features.home_attack_strength == pytest.approx(
            2.0 / 1.5, abs=0.01  # 2.0 / league_avg_home_goals
        )

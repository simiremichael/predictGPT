from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_prediction_service_connects_ai_to_match_research() -> None:
    from prediction.service import PredictionService

    service = PredictionService(ai_adjustment_layer=object())
    with (
        patch("ai.service.AIService") as ai_service,
        patch("web_research.service.MatchResearchService") as research_service,
    ):
        service._ensure_research_components()

    research_service.assert_called_once_with(ai_service=ai_service.return_value)


@pytest.mark.asyncio
async def test_orchestrator_returns_persisted_prediction_id() -> None:
    from services.prediction_orchestrator import PredictionOrchestrator

    prediction = SimpleNamespace(
        prediction_id="prediction-1",
        model="poisson-ai",
        model_version="test",
        data_quality=0.9,
        ai_adjustment=SimpleNamespace(applied=True),
        research=SimpleNamespace(available=True),
    )
    service = MagicMock()
    service.predict_match = AsyncMock(return_value=prediction)

    with (
        patch("prediction.service.PredictionService", return_value=service),
        patch("core.cache.invalidate_cache_keys", new=AsyncMock()),
    ):
        prediction_id = await PredictionOrchestrator()._run_pipeline(
            "match-1",
            db_session=object(),
            include_research=True,
            prediction_context=object(),
        )

    assert prediction_id == "prediction-1"
    service.predict_match.assert_awaited_once()


@pytest.mark.asyncio
async def test_batch_selection_targets_current_season_unplayed_matches() -> None:
    from services.prediction_orchestrator import PredictionOrchestrator

    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    database = AsyncMock()
    database.execute = AsyncMock(return_value=result)

    summary = await PredictionOrchestrator().generate_upcoming_predictions(db_session=database)

    query = str(database.execute.await_args.args[0])
    assert "seasons.is_current IS true" in query
    assert "matches.is_finished IS false" in query
    assert "matches.status =" in query
    assert "matches.kickoff_at >=" in query
    assert "matches.kickoff_at <=" in query
    assert summary["total_matches"] == 0


@pytest.mark.asyncio
async def test_team_statistics_are_scoped_to_match_league_and_season() -> None:
    from services.prediction_data import PredictionDataService

    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    database = AsyncMock()
    database.execute = AsyncMock(return_value=result)
    service = PredictionDataService(provider=MagicMock())

    await service._load_latest_team_statistics(
        database, "team-1", "league-1", "season-1"
    )

    query = str(database.execute.await_args.args[0])
    assert "team_statistics.league_id =" in query
    assert "team_statistics.season_id =" in query


@pytest.mark.asyncio
async def test_fixture_sync_refreshes_existing_blank_match_fields() -> None:
    from api.v1.endpoints import providers as provider_routes

    database = AsyncMock()
    kickoff = datetime(2026, 10, 3, 15)

    await provider_routes._save_fixtures(
        database,
        [
            {
                "provider": "sportmonks",
                "provider_fixture_id": "fixture-1",
                "league_id": "league-1",
                "season_id": "season-1",
                "home_team_id": "home-1",
                "away_team_id": "away-1",
                "home_team_name": "Home FC",
                "away_team_name": "Away FC",
                "kickoff_at": kickoff,
                "venue": "City Stadium",
                "status": "scheduled",
                "is_finished": False,
                "provider_metadata": {"refreshed": True},
            },
        ],
    )

    # _save_fixtures now writes the match rows as a single bulk upsert.
    statement = database.execute.await_args.args[0]
    sql = str(statement.compile())
    assert "ON CONFLICT" in sql.upper()
    # COALESCE keeps a stored value when the provider omits the field.
    assert "COALESCE" in sql.upper()

    params = str(statement.compile().params)
    assert "fixture-1" in params
    assert "league-1" in params
    assert "season-1" in params
    assert "Home FC" in params
    assert "City Stadium" in params


@pytest.mark.asyncio
async def test_prediction_history_includes_home_and_away_team_names() -> None:
    from api.v1.endpoints import predictions as prediction_routes

    prediction = SimpleNamespace(
        id="prediction-1",
        match_id="match-1",
        model_version="poisson-ai",
        prediction_version="v1",
        generated_at=datetime.now(UTC),
        feature_snapshot={"data_quality": 0.8},
        confidence=0.75,
        home_probability=0.5,
        draw_probability=0.25,
        away_probability=0.25,
        over_2_5_probability=0.55,
        under_2_5_probability=0.45,
        btts_probability=0.5,
        ai_adjustment_json={"applied": True},
        context_hash="context-hash",
        admin_verify_gg=None,
        admin_verify_win=None,
        admin_verify_over_2_5=None,
    )
    count_result = MagicMock()
    count_result.scalar.return_value = 1
    rows_result = MagicMock()
    rows_result.all.return_value = [
        (prediction, "Home FC", "Away FC", None, "scheduled", None, None)
    ]
    database = AsyncMock()
    database.execute = AsyncMock(side_effect=[count_result, rows_result])

    with (
        patch.object(prediction_routes, "get_cached", new=AsyncMock(return_value=None)),
        patch.object(prediction_routes, "set_cached", new=AsyncMock()),
        patch.object(prediction_routes, "_is_subscribed", new=AsyncMock(return_value=False)),
    ):
        response = await prediction_routes.list_predictions(
            request=MagicMock(),
            db=database,
            page=1,
            page_size=20,
            match_id=None,
            league_id=None,
            team_id=None,
            model_version=None,
            date_from=None,
            date_to=None,
            kickoff_date=None,
            played=None,
            upcoming_only=False,
            min_elapsed_minutes=None,
            max_elapsed_minutes=None,
            newest_first=False,
            user_email=None,
        )

    assert response["data"][0]["match_home_team"] == "Home FC"
    assert response["data"][0]["match_away_team"] == "Away FC"


def test_research_status_requires_saved_search_sources() -> None:
    from api.v1.endpoints.predictions import _prediction_has_research

    no_sources = SimpleNamespace(
        news_snapshot={"research": {"available": True, "sources_count": 0}, "sources": []},
        ai_evidence_json=[],
    )
    with_sources = SimpleNamespace(
        news_snapshot={"research": {"available": True, "sources_count": 1}, "sources": [{}]},
        ai_evidence_json=[],
    )

    assert _prediction_has_research(no_sources) is False
    assert _prediction_has_research(with_sources) is True

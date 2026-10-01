from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_team_statistics_uses_database_before_provider() -> None:
    from api.v1.endpoints import providers as provider_routes

    database_rows = {
        "data": [{"team_id": "team-1", "games_played": 8}],
        "meta": {"page": 1, "page_size": 50, "total": 1, "total_pages": 1},
    }
    with (
        patch.object(
            provider_routes,
            "_read_db_resource_payload",
            new=AsyncMock(return_value=database_rows),
        ),
        patch.object(provider_routes, "get_football_provider") as provider_factory,
    ):
        response = await provider_routes._provider_data_response(
            "get_team_statistics", team_id="team-1"
        )

    assert response["data"] == database_rows["data"]
    assert response["meta"]["source"] == "database"
    provider_factory.assert_not_called()


@pytest.mark.asyncio
async def test_team_statistics_fetches_saves_and_rereads_on_database_miss() -> None:
    from api.v1.endpoints import providers as provider_routes

    provider_statistics = {
        "provider": "api_football",
        "provider_team_id": "provider-team-1",
        "league_id": "provider-league-1",
        "season_id": "season-2026",
        "games_played": 8,
        "wins": 5,
    }
    empty_rows = {
        "data": [],
        "meta": {"page": 1, "page_size": 50, "total": 0, "total_pages": 1},
    }
    saved_rows = {
        "data": [{"team_id": "team-1", "games_played": 8, "wins": 5}],
        "meta": {"page": 1, "page_size": 50, "total": 1, "total_pages": 1},
    }
    provider = AsyncMock()
    provider.connect = AsyncMock()
    provider.close = AsyncMock()
    provider.get_team_statistics = AsyncMock(return_value=provider_statistics)
    mapping = SimpleNamespace(
        provider_team_id="provider-team-1",
        provider_league_id="provider-league-1",
        season_id="season-2026",
    )
    db_session = AsyncMock()
    mapping_result = MagicMock()
    mapping_result.scalar_one_or_none.return_value = mapping
    db_session.execute = AsyncMock(return_value=mapping_result)

    class SessionContext:
        async def __aenter__(self):
            return db_session

        async def __aexit__(self, *_args):
            return False

    with (
        patch.object(
            provider_routes,
            "_read_db_resource_payload",
            new=AsyncMock(side_effect=[empty_rows, saved_rows]),
        ) as read_database,
        patch.object(provider_routes, "_save_provider_data_to_db", new=AsyncMock()) as save_data,
        patch.object(provider_routes, "AsyncSessionLocal", return_value=SessionContext()),
        patch.object(provider_routes, "get_football_provider", return_value=provider),
    ):
        response = await provider_routes._provider_data_response(
            "get_team_statistics", team_id="team-1"
        )

    assert response["data"] == saved_rows["data"]
    assert response["meta"]["source"] == "database"
    assert read_database.await_count == 2
    provider.get_team_statistics.assert_awaited_once_with(
        team_id="provider-team-1",
        league_id="provider-league-1",
        season_id="season-2026",
    )
    save_data.assert_awaited_once_with("get_team_statistics", [provider_statistics])


@pytest.mark.asyncio
async def test_standings_saver_awaits_insert_and_links_internal_team() -> None:
    from api.v1.endpoints import providers as provider_routes

    mapping_result = MagicMock()
    mapping_result.scalar_one_or_none.return_value = "team-1"
    existing_result = MagicMock()
    existing_result.scalar_one_or_none.return_value = None
    database = AsyncMock()
    database.execute = AsyncMock(side_effect=[mapping_result, existing_result, None])

    await provider_routes._save_standings(
        database,
        [
            {
                "provider": "api_football",
                "provider_team_id": "provider-team-1",
                "league_id": "league-1",
                "season_id": "season-1",
                "games_played": 8,
                "wins": 5,
            }
        ],
    )

    assert database.execute.await_count == 3
    insert_statement = database.execute.await_args_list[-1].args[0]
    assert insert_statement.compile().params["internal_team_id"] == "team-1"
    assert insert_statement.compile().params["games_played"] == 8


@pytest.mark.asyncio
async def test_standings_payload_matches_league_page_contract() -> None:
    from api.v1.endpoints import providers as provider_routes

    stats = SimpleNamespace(
        internal_team_id="team-1",
        provider_team_id="provider-team-1",
        league_id="league-1",
        season_id="season-1",
        position=1,
        points=20,
        games_played=8,
        wins=6,
        draws=2,
        losses=0,
        goals_for=18,
        goals_against=4,
        clean_sheets=5,
        is_home=False,
        form_rating=None,
        average_possession=None,
        average_shots=None,
        average_xg=None,
        average_xga=None,
        goals_per_game=None,
        goals_conceded_per_game=None,
    )
    count_result = MagicMock()
    count_result.scalar.return_value = 1
    rows_result = MagicMock()
    rows_result.all.return_value = [(stats, "Example FC")]
    database = AsyncMock()
    database.execute = AsyncMock(side_effect=[count_result, rows_result])

    class SessionContext:
        async def __aenter__(self):
            return database

        async def __aexit__(self, *_args):
            return False

    with patch.object(provider_routes, "AsyncSessionLocal", return_value=SessionContext()):
        payload = await provider_routes._read_db_resource_payload(
            "get_standings", league_id="league-1"
        )

    standing = payload["data"][0]
    assert standing["team_id"] == "team-1"
    assert standing["team_name"] == "Example FC"
    assert standing["played"] == 8
    assert standing["goal_difference"] == 14

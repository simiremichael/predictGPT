from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_match_detail_endpoint_awaits_detail_builder() -> None:
    from api.v1.endpoints import matches as match_routes

    match = MagicMock(id="match-1")
    query_result = MagicMock()
    query_result.scalar_one_or_none.return_value = match
    database = AsyncMock()
    database.execute = AsyncMock(return_value=query_result)
    expected_detail = {
        "id": "match-1",
        "home_team": {"id": "home-1", "name": "Home FC"},
        "away_team": {"id": "away-1", "name": "Away FC"},
    }

    with (
        patch.object(match_routes, "get_cached", new=AsyncMock(return_value=None)),
        patch.object(
            match_routes,
            "_build_match_detail",
            new=AsyncMock(return_value=expected_detail),
        ) as build_detail,
        patch.object(match_routes, "set_cached", new=AsyncMock()),
    ):
        response = await match_routes.get_match(
            request=MagicMock(), match_id="match-1", db=database
        )

    assert response["data"] == expected_detail
    build_detail.assert_awaited_once_with(match, database)


@pytest.mark.asyncio
async def test_match_detail_builder_loads_teams_by_foreign_key() -> None:
    from api.v1.endpoints import matches as match_routes

    match = SimpleNamespace(
        id="match-1",
        league_id="league-1",
        season_id=None,
        home_team_id="home-1",
        away_team_id="away-1",
        home_team_name=None,
        away_team_name=None,
        kickoff_at=None,
        status="scheduled",
        venue=None,
        referee=None,
        home_score=None,
        away_score=None,
        is_finished=False,
        retrieved_at=None,
        league=SimpleNamespace(name="Premier League"),
    )
    home_team = SimpleNamespace(
        id="home-1", name="Home FC", logo_url="home.png", venue_city="London"
    )
    away_team = SimpleNamespace(
        id="away-1", name="Away FC", logo_url="away.png", venue_city="Madrid"
    )
    match_result = MagicMock()
    match_result.scalar_one.return_value = match
    teams_result = MagicMock()
    teams_result.scalars.return_value.all.return_value = [home_team, away_team]
    no_row = MagicMock()
    no_row.scalar_one_or_none.return_value = None
    no_rows = MagicMock()
    no_rows.scalars.return_value.all.return_value = []
    database = AsyncMock()
    database.execute = AsyncMock(
        side_effect=[
            match_result,
            teams_result,
            no_row,
            no_row,
            no_row,
            no_rows,
            no_rows,
            no_rows,
            no_row,
        ]
    )

    detail = await match_routes._build_match_detail(match, database)

    assert detail["home_team"] == {
        "id": "home-1",
        "name": "Home FC",
        "logo_url": "home.png",
        "venue_city": "London",
    }
    assert detail["away_team"] == {
        "id": "away-1",
        "name": "Away FC",
        "logo_url": "away.png",
        "venue_city": "Madrid",
    }

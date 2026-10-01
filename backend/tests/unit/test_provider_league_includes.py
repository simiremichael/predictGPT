from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_league_includes_merge_raw_provider_relations() -> None:
    from api.v1.endpoints import providers as provider_routes

    includes = "sport,country,currentSeason,seasons"
    current_season = {"id": 2026, "name": "2026"}
    season_list = [current_season]
    provider = AsyncMock()
    provider.provider_name = "sportmonks"
    provider.connect = AsyncMock()
    provider.close = AsyncMock()
    provider.http.get_league = AsyncMock(
        return_value={
            "sport": {"name": "Football"},
            "country": {"name": "England"},
            "currentseason": current_season,
            "seasons": season_list,
        }
    )
    rows = [
        {
            "id": "league-1",
            "name": "Premier League",
            "country": "England",
            "current_season": None,
        }
    ]

    with patch.object(provider_routes, "get_football_provider", return_value=provider):
        result = await provider_routes._attach_league_includes("39", includes, rows)

    provider.http.get_league.assert_awaited_once_with(
        "39", includes=["sport", "country", "currentSeason", "seasons"]
    )
    assert result[0]["sport"] == {"name": "Football"}
    assert result[0]["country"] == "England"
    assert result[0]["country_details"] == {"name": "England"}
    assert result[0]["currentseason"] == current_season
    assert result[0]["current_season"] == current_season
    assert result[0]["seasons"] == season_list


@pytest.mark.asyncio
async def test_league_includes_are_attached_after_database_miss() -> None:
    from api.v1.endpoints import providers as provider_routes

    includes = "currentSeason,seasons"
    database_row = {
        "id": "39",
        "name": "Premier League",
        "current_season": None,
    }
    empty_payload = {
        "data": [],
        "meta": {"page": 1, "page_size": 1, "total": 0, "total_pages": 1},
    }
    saved_payload = {
        "data": [database_row.copy()],
        "meta": {"page": 1, "page_size": 1, "total": 1, "total_pages": 1},
    }
    provider = AsyncMock()
    provider.connect = AsyncMock()
    provider.close = AsyncMock()
    provider.get_league = AsyncMock(
        return_value={"provider_league_id": "39", "name": "Premier League"}
    )
    provider.provider_name = "sportmonks"
    provider.http.get_league = AsyncMock(
        return_value={
            "currentseason": {"id": 2026, "name": "2026"},
            "seasons": [{"id": 2026, "name": "2026"}],
        }
    )

    with (
        patch.object(
            provider_routes,
            "_read_db_resource_payload",
            new=AsyncMock(side_effect=[empty_payload, saved_payload]),
        ),
        patch.object(provider_routes, "_save_provider_data_to_db", new=AsyncMock()),
        patch.object(provider_routes, "get_football_provider", return_value=provider),
    ):
        response = await provider_routes._provider_data_response(
            "get_league", league_id="39", include=includes
        )

    assert response["data"][0]["current_season"] == {
        "id": 2026,
        "name": "2026",
    }
    assert response["data"][0]["seasons"] == [{"id": 2026, "name": "2026"}]
    assert response["meta"]["include"] == includes
    provider.http.get_league.assert_awaited_once_with("39", includes=["currentSeason", "seasons"])

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from football_data.sportmonks import SportmonksProvider


@pytest.mark.asyncio
async def test_sportmonks_get_fixture_requests_relations_and_normalizes_v3_shape() -> None:
    raw_fixture = {
        "id": 19049276,
        "league_id": 8,
        "season_id": 27,
        "starting_at": "2026-10-03T15:00:00Z",
        "state": {"state": "NS"},
        "venue": {"name": "Example Stadium"},
        "participants": [
            {"id": 101, "name": "Home FC", "meta": {"location": "home"}},
            {"id": 202, "name": "Away FC", "meta": {"location": "away"}},
        ],
    }
    provider = object.__new__(SportmonksProvider)
    provider.http = MagicMock()
    provider.http.get_fixture = AsyncMock(return_value=raw_fixture)

    fixture = await provider.get_fixture("19049276")

    provider.http.get_fixture.assert_awaited_once_with(
        "19049276",
        includes=["participants"],
    )
    assert fixture is not None
    assert fixture.provider_fixture_id == "19049276"
    assert fixture.home_team_id == "101"
    assert fixture.home_team_name == "Home FC"
    assert fixture.away_team_id == "202"
    assert fixture.away_team_name == "Away FC"
    assert fixture.league_id == "8"
    assert fixture.season_id == "27"
    assert fixture.kickoff_at == datetime.fromisoformat("2026-10-03T15:00:00+00:00")
    assert fixture.venue == "Example Stadium"


@pytest.mark.asyncio
async def test_sportmonks_get_fixtures_includes_participants_for_sync() -> None:
    raw_fixture = {
        "id": 19049276,
        "league_id": "8",
        "season_id": "27",
        "starting_at": "2026-10-03T15:00:00Z",
        "participants": [
            {"id": 101, "name": "Home FC", "meta": {"location": "home"}},
            {"id": 202, "name": "Away FC", "meta": {"location": "away"}},
        ],
    }
    provider = object.__new__(SportmonksProvider)
    provider.http = MagicMock()
    provider.http.get_fixtures = AsyncMock(return_value=[raw_fixture])

    fixtures = await provider.get_fixtures(league_id="8", season_id="27")

    provider.http.get_fixtures.assert_awaited_once_with(
        params={"league_id": "8", "season_id": "27"},
        includes=["participants"],
    )
    assert fixtures[0].home_team_name == "Home FC"
    assert fixtures[0].away_team_name == "Away FC"


@pytest.mark.asyncio
async def test_incomplete_match_refresh_persists_provider_fields_and_mapped_ids() -> None:
    from api.v1.endpoints import matches as match_routes
    from football_data.models import NormalizedFixture

    fixture = NormalizedFixture(
        provider="sportmonks",
        provider_fixture_id="19049276",
        league_id="provider-league-8",
        provider_league_id="provider-league-8",
        season_id=None,
        home_team_id="provider-team-101",
        away_team_id="provider-team-202",
        home_team_name="Home FC",
        away_team_name="Away FC",
        kickoff_at=datetime(2026, 10, 3, 15, 0),
        venue="Example Stadium",
        provider_metadata={"league_name": "Premier League"},
    )
    provider = AsyncMock()
    provider.connect = AsyncMock()
    provider.close = AsyncMock()
    provider.get_fixture = AsyncMock(return_value=fixture)
    match = SimpleNamespace(
        id="19049276",
        provider_fixture_id="19049276",
        provider_name="sportmonks",
        home_team_name=None,
        away_team_name=None,
        kickoff_at=None,
        league_id=None,
        season_id=None,
        home_team_id=None,
        away_team_id=None,
        venue=None,
        referee=None,
        home_score=None,
        away_score=None,
        status="scheduled",
        is_finished=False,
        provider_metadata={},
        retrieved_at=None,
    )
    mapping_results = []
    for mapped_id in ("league-internal-8", "team-internal-101", "team-internal-202"):
        result = MagicMock()
        result.scalar_one_or_none.return_value = mapped_id
        mapping_results.append(result)
    database = AsyncMock()
    database.execute = AsyncMock(side_effect=mapping_results)

    with patch("football_data.factory.get_football_provider", return_value=provider):
        await match_routes._refresh_incomplete_match(match, database)

    provider.get_fixture.assert_awaited_once_with("19049276")
    assert match.home_team_name == "Home FC"
    assert match.away_team_name == "Away FC"
    assert match.kickoff_at == datetime(2026, 10, 3, 15, 0)
    assert match.league_id == "league-internal-8"
    assert match.home_team_id == "team-internal-101"
    assert match.away_team_id == "team-internal-202"
    assert match.provider_metadata["league_name"] == "Premier League"
    database.commit.assert_awaited_once()

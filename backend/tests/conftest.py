"""Shared test fixtures for the Football AI test suite."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

APP_ROOT = Path(__file__).resolve().parents[2] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from football_data.api_football import APIFootballProvider  # noqa: E402
from football_data.sportmonks import SportmonksProvider  # noqa: E402

# ── Mock data: API-Football style ──────────────────────────────────────────
MOCK_API_FOOTBALL_FIXTURE: dict[str, Any] = {
    "fixture": {
        "id": 12345,
        "referee": "M. Oliver",
        "timezone": "UTC",
        "date": "2024-05-19T15:00:00+00:00",
        "timestamp": 1716126000,
        "venue": {"id": 68, "name": "Emirates Stadium", "city": "London"},
        "status": {"long": "Scheduled", "short": "suspended"},
    },
    "league": {"id": 39, "name": "Premier League", "season": 2023, "round": "Regular Season"},
    "teams": {
        "home": {"id": 42, "name": "Arsenal", "winner": None},
        "away": {"id": 52, "name": "Manchester City", "winner": None},
    },
    "goals": {"home": None, "away": None},
}

MOCK_API_FOOTBALL_TEAM: dict[str, Any] = {
    "team": {
        "id": 42,
        "name": "Arsenal",
        "code": "ARS",
        "country": "England",
        "founded": 1886,
        "logo": "https://media.api-sports.io/football/teams/42.png",
    },
    "venue": {"id": 68, "name": "Emirates Stadium", "city": "London", "capacity": 60704},
}

MOCK_API_FOOTBALL_LEAGUE: dict[str, Any] = {
    "league": {
        "id": 39,
        "name": "Premier League",
        "country": "England",
        "code": "GB",
        "season_count": 5,
        "type": "League",
        "logo": "https://media.api-sports.io/football/leagues/39.png",
    },
}

MOCK_API_FOOTBALL_INJURY: dict[str, Any] = {
    "player": {"id": 2538, "name": "Gabriel Magalhaes", "number": 6, "position": "Defender", "reason": "Muscle injury"},
    "team": {"id": 42, "name": "Arsenal"},
    "fixture": {"id": 12345},
    "player_id": 2538,
    "team_id": 42,
}

MOCK_API_FOOTBALL_LINEUP: dict[str, Any] = {
    "fixture": {"id": 12345},
    "team": {"id": 42, "name": "Arsenal"},
    "formation": {"formation": "4-2-3-1", "lineup": [
        {"player": {"name": "Aaron Ramsdale"}, "pos": "GK"},
        {"player": {"name": "William Saliba"}, "pos": "D"},
    ], "substitutes": [
        {"player": {"name": "Matheus Nascimento"}, "pos": "GK"},
    ]},
}


# ── Mock data: Sportmonks style ───────────────────────────────────────────
MOCK_SPORTMONKS_FIXTURE: dict[str, Any] = {
    "id": 12345,
    "league": {"id": "39", "name": "Premier League", "season_id": "2023"},
    "home": {"team_id": 42, "name": "Arsenal"},
    "away": {"team_id": 52, "name": "Manchester City"},
    "state": {"state": "scheduled"},
    "starting_at": {"date": "2024-05-19", "time": "15:00", "datetime": "2024-05-19T15:00:00.000000Z"},
    "venue": {"name": "Emirates Stadium"},
    "referee": {"name": "M. Oliver"},
    "home_score": None,
    "away_score": None,
}

MOCK_SPORTMONKS_TEAM: dict[str, Any] = {
    "id": 42,
    "name": "Arsenal",
    "short_code": "ARS",
    "founded": 1886,
    "logo_path": "https://cdn.sportmonks.com/teams/42.png",
    "venue": {"name": "Emirates Stadium", "city": "London"},
}

MOCK_SPORTMONKS_LEAGUE: dict[str, Any] = {
    "id": 39,
    "name": "Premier League",
    "country": "England",
    "iso2": "GB",
}

MOCK_SPORTMONKS_INJURY: dict[str, Any] = {
    "player": {"id": 2538, "name": "Gabriel Magalhaes", "position": "Defender", "jersey_number": 6},
    "team": {"id": 42, "name": "Arsenal"},
    "injury": {"type": "Muscle injury", "severity": "out", "description": "Hamstring injury", "start_date": "2024-05-10", "return_date": None},
}


# ── Provider fixtures ──────────────────────────────────────────────────────
@pytest.fixture
def api_football_provider() -> APIFootballProvider:
    return APIFootballProvider(api_key="test_key", base_url="https://v3.football.api-sports.io")


@pytest.fixture
def sportmonks_provider() -> SportmonksProvider:
    return SportmonksProvider(api_token="test_token", base_url="https://api.sportmonks.com/v3/football")


@pytest.fixture
def mock_http_response() -> MagicMock:
    """Return a mock that simulates a successful httpx response."""
    mock = MagicMock()
    mock.status_code = 200
    mock.headers = {}
    mock.text = "{}"
    mock.json.return_value = {"response": [], "results": 0}
    return mock

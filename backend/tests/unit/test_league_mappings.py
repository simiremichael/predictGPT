"""Tests for league mappings and provider ID resolution."""

from __future__ import annotations

from football_data.league_mappings import LeagueConfig, LeagueMapping


def test_default_leagues_registered() -> None:
    leagues = LeagueMapping.all()
    internal_ids = [league.internal_id for league in leagues]
    assert "premier_league" in internal_ids
    assert "la_liga" in internal_ids
    assert "serie_a" in internal_ids
    assert "bundesliga" in internal_ids
    assert "ligue_1" in internal_ids
    assert "champions_league" in internal_ids
    assert "europa_league" in internal_ids


def test_api_football_ids_registered() -> None:
    cfg = LeagueMapping.get("premier_league")
    assert cfg is not None
    af_ids = cfg.provider_ids.get("api_football")
    assert af_ids is not None
    assert af_ids["league_id"] == "39"
    assert af_ids["season_id"] == "2026"


def test_sportmonks_ids_registered() -> None:
    cfg = LeagueMapping.get("premier_league")
    assert cfg is not None
    sm_ids = cfg.provider_ids.get("sportmonks")
    assert sm_ids is not None
    assert "league_id" in sm_ids


def test_get_provider_league_id() -> None:
    result = LeagueMapping.get_provider_league_id("premier_league", "api_football")
    assert result is not None
    league_id, season_id = result
    assert league_id == "39"
    assert season_id == "2026"


def test_get_provider_league_id_missing_provider() -> None:
    result = LeagueMapping.get_provider_league_id("premier_league", "nonexistent")
    assert result is None


def test_register_custom_league() -> None:
    custom = LeagueConfig("test_league", "Test League", "TestLand")
    custom.add_provider("api_football", "999", "2024")
    LeagueMapping.register(custom)
    cfg = LeagueMapping.get("test_league")
    assert cfg is not None
    assert cfg.name == "Test League"


def test_by_provider_lookup() -> None:
    cfg = LeagueMapping.by_provider("api_football", "39")
    assert cfg is not None
    assert cfg.internal_id == "premier_league"

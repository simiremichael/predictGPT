"""Provider-specific league and season ID mappings.

API-Football and Sportmonks use different identifiers for the same
competition.  This module centralises those mappings so no league IDs are
hardcoded in the prediction engine, sync jobs, or frontend code.

When adding a new competition, add an entry here with ``internal_id`` and
the per-provider IDs.
"""
from __future__ import annotations

from typing import Literal

ProviderName = Literal["api_football", "sportmonks"]


class LeagueMapping:
    """Static mapping table between internal league IDs and provider IDs."""

    #: internal_id -> LeagueConfig
    _LEAGUES: dict[str, LeagueConfig] = {}

    @classmethod
    def register(cls, config: LeagueConfig) -> None:
        cls._LEAGUES[config.internal_id] = config

    @classmethod
    def get(cls, internal_id: str) -> LeagueConfig | None:
        return cls._LEAGUES.get(internal_id)

    @classmethod
    def all(cls) -> list[LeagueConfig]:
        return list(cls._LEAGUES.values())

    @classmethod
    def by_provider(cls, provider: ProviderName, provider_league_id: str) -> LeagueConfig | None:
        for cfg in cls._LEAGUES.values():
            ids = cfg.provider_ids.get(provider)
            if ids and ids.get("league_id") == provider_league_id:
                return cfg
        return None

    @classmethod
    def get_provider_league_id(
        cls, internal_id: str, provider: ProviderName
    ) -> tuple[str, str] | None:
        """Return (provider_league_id, provider_season_id) for a given internal id."""
        cfg = cls._LEAGUES.get(internal_id)
        if cfg is None:
            return None
        ids = cfg.provider_ids.get(provider)
        if ids is None:
            return None
        return ids.get("league_id", ""), ids.get("season_id", "")


class LeagueConfig:
    """Configuration for a single competition across providers."""

    def __init__(
        self,
        internal_id: str,
        name: str,
        country: str | None = None,
        provider_ids: dict[ProviderName, dict[str, str]] | None = None,
    ) -> None:
        self.internal_id = internal_id
        self.name = name
        self.country = country
        self.provider_ids: dict[ProviderName, dict[str, str]] = provider_ids or {}

    def add_provider(
        self, provider: ProviderName, league_id: str, season_id: str
    ) -> None:
        self.provider_ids[provider] = {
            "league_id": league_id,
            "season_id": season_id,
        }


def _register_default_leagues() -> None:
    leagues: list[tuple[str, str, str | None]] = [
        ("premier_league", "Premier League", "England"),
        ("championship", "EFL Championship", "England"),
        ("league_one", "EFL League One", "England"),
        ("la_liga", "La Liga", "Spain"),
        ("segunda_division", "Segunda División", "Spain"),
        ("serie_a", "Serie A", "Italy"),
        ("serie_b", "Serie B", "Italy"),
        ("bundesliga", "Bundesliga", "Germany"),
        ("bundesliga_2", "2. Bundesliga", "Germany"),
        ("ligue_1", "Ligue 1", "France"),
        ("ligue_2", "Ligue 2", "France"),
        ("primeira_liga", "Primeira Liga", "Portugal"),
        ("liga_portugal_2", "Liga Portugal 2", "Portugal"),
        ("super_lig", "Süper Lig", "Turkey"),
        ("tff_1_lig", "TFF 1. Lig", "Turkey"),
        ("super_league", "Super League 1", "Greece"),
        ("football_league", "Football League", "Greece"),
        ("swiss_super_league", "Swiss Super League", "Switzerland"),
        ("challenge_league", "Swiss Challenge League", "Switzerland"),
        ("eredivisie", "Eredivisie", "Netherlands"),
        ("eerste_divisie", "Eerste Divisie", "Netherlands"),
        ("jupiler_pro_league", "Jupiler Pro League", "Belgium"),
        ("challenger_pro_league", "Challenger Pro League", "Belgium"),
        ("champions_league", "UEFA Champions League", None),
        ("europa_league", "UEFA Europa League", None),
        ("conference_league", "UEFA Conference League", None),
    ]
    for internal_id, name, country in leagues:
        LeagueMapping.register(LeagueConfig(internal_id, name, country))


_register_default_leagues()

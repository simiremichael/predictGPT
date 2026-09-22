"""Abstract base class defining the FootballDataProvider interface.

Both API-Football and Sportmonks providers implement this interface.  The
prediction engine and all other application layers communicate only with
``FootballDataProvider``, never with a concrete provider, enabling provider
switching at runtime via configuration.

All methods are async.  Query parameters use ``**kwargs`` for flexibility,
but every implementation MUST accept at minimum the documented named
parameters so the interface is uniform.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from football_data.models import (
    NormalizedFixture,
    NormalizedForm,
    NormalizedHeadToHead,
    NormalizedInjury,
    NormalizedLeague,
    NormalizedLineup,
    NormalizedMatchStatistics,
    NormalizedOdds,
    NormalizedOddsMarket,
    NormalizedPlayer,
    NormalizedSeason,
    NormalizedStanding,
    NormalizedStandings,
    NormalizedSuspension,
    NormalizedTeam,
    NormalizedTeamStatistics,
)


class FootballDataProvider(ABC):
    """Abstract interface for all football data providers."""

    provider_name: str

    @abstractmethod
    async def connect(self) -> None:
        """Initialize any provider network resources."""

    @abstractmethod
    async def close(self) -> None:
        """Release any provider network resources."""

    # ── Generic helpers ─────────────────────────────────────────────── #
    @abstractmethod
    async def get_leagues(self, **kwargs: Any) -> list[NormalizedLeague]:
        """Return all available leagues."""

    @abstractmethod
    async def get_league(self, league_id: str, **kwargs: Any) -> NormalizedLeague | None:
        """Return a single league by provider league id."""

    @abstractmethod
    async def get_seasons(
        self, league_id: str | None = None, **kwargs: Any
    ) -> list[NormalizedSeason]:
        """Return seasons for a league (or all leagues)."""

    @abstractmethod
    async def get_teams(
        self, league_id: str | None = None, season_id: str | None = None, **kwargs: Any
    ) -> list[NormalizedTeam]:
        """Return teams in a league/season."""

    @abstractmethod
    async def get_team(self, team_id: str, **kwargs: Any) -> NormalizedTeam | None:
        """Return a single team."""

    @abstractmethod
    async def get_team_statistics(
        self,
        team_id: str,
        league_id: str | None = None,
        season_id: str | None = None,
        **kwargs: Any,
    ) -> NormalizedTeamStatistics | None:
        """Return season/team statistics."""

    @abstractmethod
    async def get_team_form(
        self, team_id: str, fixture_id: str | None = None, **kwargs: Any
    ) -> NormalizedForm | None:
        """Return recent form / last-N results for a team."""

    @abstractmethod
    async def get_fixtures(
        self,
        league_id: str | None = None,
        season_id: str | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        team_id: str | None = None,
        **kwargs: Any,
    ) -> list[NormalizedFixture]:
        """Return fixtures matching the filters."""

    @abstractmethod
    async def get_fixture(self, fixture_id: str, **kwargs: Any) -> NormalizedFixture | None:
        """Return a single fixture by provider fixture id."""

    @abstractmethod
    async def get_head_to_head(
        self, team_a_id: str, team_b_id: str, league_id: str | None = None, **kwargs: Any
    ) -> NormalizedHeadToHead | None:
        """Return head-to-head history between two teams."""

    @abstractmethod
    async def get_injuries(
        self, team_id: str | None = None, fixture_id: str | None = None, **kwargs: Any
    ) -> list[NormalizedInjury]:
        """Return injuries, optionally filtered by team or fixture."""

    @abstractmethod
    async def get_suspensions(
        self, team_id: str | None = None, fixture_id: str | None = None, **kwargs: Any
    ) -> list[NormalizedSuspension]:
        """Return suspensions / sidelined players."""

    @abstractmethod
    async def get_lineups(
        self, fixture_id: str, **kwargs: Any
    ) -> dict[str, NormalizedLineup] | list[NormalizedLineup]:
        """Return confirmed lineups for a fixture."""

    @abstractmethod
    async def get_predicted_lineups(
        self, fixture_id: str, **kwargs: Any
    ) -> NormalizedLineup | None:
        """Return predicted lineups for a fixture."""

    @abstractmethod
    async def get_match_statistics(
        self, fixture_id: str, **kwargs: Any
    ) -> NormalizedMatchStatistics | None:
        """Return post-match statistics for a fixture."""

    @abstractmethod
    async def get_odds(self, fixture_id: str | None = None, **kwargs: Any) -> NormalizedOdds | None:
        """Return odds for a fixture."""

    @abstractmethod
    async def get_players(
        self, team_id: str | None = None, **kwargs: Any
    ) -> list[NormalizedPlayer]:
        """Return players, optionally filtered by team."""

    @abstractmethod
    async def get_standings(
        self, league_id: str | None = None, season_id: str | None = None, **kwargs: Any
    ) -> NormalizedStandings | None:
        """Return league standings."""

    @abstractmethod
    async def get_timezones(self, **kwargs: Any) -> list[str]:
        """Return supported timezone names or timezone metadata."""

    @abstractmethod
    async def get_countries(self, **kwargs: Any) -> list[dict[str, Any]]:
        """Return country metadata."""

    @abstractmethod
    async def get_venues(
        self, venue_id: str | None = None, team_id: str | None = None, **kwargs: Any
    ) -> list[dict[str, Any]]:
        """Return venue metadata, optionally filtered by venue or team."""

    @abstractmethod
    async def get_coaches(
        self, team_id: str | None = None, coach_id: str | None = None, **kwargs: Any
    ) -> list[dict[str, Any]]:
        """Return coach metadata, optionally filtered by team or coach."""

    @abstractmethod
    async def get_transfers(
        self, player_id: str | None = None, team_id: str | None = None, **kwargs: Any
    ) -> list[dict[str, Any]]:
        """Return transfer records, optionally filtered by player or team."""

    @abstractmethod
    async def get_trophies(
        self, player_id: str | None = None, team_id: str | None = None, **kwargs: Any
    ) -> list[dict[str, Any]]:
        """Return trophy metadata, optionally filtered by player or team."""

    @abstractmethod
    async def get_predictions(self, fixture_id: str, **kwargs: Any) -> list[dict[str, Any]]:
        """Return fixture prediction data."""

    @abstractmethod
    async def get_sidelined(
        self, team_id: str | None = None, fixture_id: str | None = None, **kwargs: Any
    ) -> list[dict[str, Any]]:
        """Return sidelined or suspended player data."""

    @abstractmethod
    async def get_pre_match_odds(
        self, fixture_id: str | None = None, **kwargs: Any
    ) -> list[dict[str, Any]]:
        """Return pre-match odds for a fixture or query."""

    @abstractmethod
    async def get_in_play_odds(
        self, fixture_id: str | None = None, **kwargs: Any
    ) -> list[dict[str, Any]]:
        """Return live/in-play odds for a fixture or query."""

    # ── Health check ────────────────────────────────────────────────── #
    @abstractmethod
    async def health_check(self) -> bool:
        """Return True if the provider is reachable and credentials are valid."""

    # ── Cache invalidation ───────────────────────────────────────────── #
    async def invalidate_cache(self, namespace: str, *keys: str) -> None:
        """Invalidate cache entries. Override in concrete providers with Redis."""
        pass

    # ── Provider metadata ──────────────────────────────────────────── #
    @property
    def name(self) -> str:
        return self.provider_name

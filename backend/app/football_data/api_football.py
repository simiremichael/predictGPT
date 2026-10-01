"""API-Football provider implementation.

Implements the full ``FootballDataProvider`` interface by calling the
API-Football (api-sports) REST API and normalizing all responses into the
internal ``Normalized*`` models defined in ``football_data/models.py``.

The provider delegates HTTP communication to ``APIFootballClient``, which
handles authentication, timeouts, retries, rate-limiting, pagination, and
error mapping.  The provider layer is responsible only for:
    * calling the client
    * normalizing responses into ``Normalized*`` models
    * caching results in Redis (with provider-aware TTLs)

Configuration:
    API_FOOTBALL_KEY      -- API key (read from env, never hardcoded)
    API_FOOTBALL_BASE_URL -- default https://v3.football.api-sports.io

The prediction engine and all application layers communicate with this class
only through the ``FootballDataProvider`` interface.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime, timezone
from typing import Any

from core.config import get_settings
from core.exceptions import (
    ProviderConfigurationError,
    ProviderNotFoundError,
    ProviderValidationError,
)
from football_data.api_football_client import APIFootballClient
from football_data.base import FootballDataProvider
from football_data.league_mappings import LeagueMapping
from football_data.models import (
    FixtureStatus,
    InjurySeverity,
    LineupStatus,
    NormalizedFixture,
    NormalizedForm,
    NormalizedHeadToHead,
    NormalizedInjury,
    NormalizedLeague,
    NormalizedLineup,
    NormalizedLineupPlayer,
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

logger = logging.getLogger(__name__)

# API-Football league id -> internal id (registered at import on the
# central LeagueConfig so provider mappings are available everywhere)
_DEFAULT_LEAGUE_IDS_API_FOOTBALL: dict[str, tuple[str, str]] = {
    "premier_league": ("39", "2026"),
    "championship": ("40", "2026"),
    "league_one": ("41", "2026"),
    "la_liga": ("140", "2026"),
    "segunda_division": ("141", "2026"),
    "serie_a": ("135", "2026"),
    "serie_b": ("136", "2026"),
    "bundesliga": ("78", "2026"),
    "bundesliga_2": ("79", "2026"),
    "ligue_1": ("61", "2026"),
    "ligue_2": ("62", "2026"),
    "primeira_liga": ("94", "2026"),
    "liga_portugal_2": ("95", "2026"),
    "super_lig": ("203", "2026"),
    "tff_1_lig": ("204", "2026"),
    "super_league": ("197", "2026"),
    "football_league": ("198", "2026"),
    "swiss_super_league": ("207", "2026"),
    "challenge_league": ("208", "2026"),
    "eredivisie": ("88", "2026"),
    "eerste_divisie": ("89", "2026"),
    "jupiler_pro_league": ("144", "2026"),
    "challenger_pro_league": ("145", "2026"),
    "champions_league": ("2", "2026"),
    "europa_league": ("3", "2026"),
    "conference_league": ("4", "2026"),
}


def _register_api_football_league_ids() -> None:
    for internal_id, (league_id, season_id) in _DEFAULT_LEAGUE_IDS_API_FOOTBALL.items():
        cfg = LeagueMapping.get(internal_id)
        if cfg is not None:
            cfg.add_provider("api_football", league_id, season_id)  # type: ignore[arg-type]


_register_api_football_league_ids()


class APIFootballProvider(FootballDataProvider):
    """Concrete provider for the API-Football (api-sports) REST API."""

    provider_name = "api_football"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        cache_client: Any = None,
    ) -> None:
        self.api_key = api_key
        self.cache = cache_client  # Redis-backed cache (optional)
        settings = get_settings()
        self.ttls = {
            "leagues": settings.cache_ttl_leagues,
            "teams": settings.cache_ttl_teams,
            "fixtures": settings.cache_ttl_fixtures,
            "statistics": settings.cache_ttl_statistics,
            "form": settings.cache_ttl_form,
            "injuries": settings.cache_ttl_injuries,
            "lineups": settings.cache_ttl_lineups,
            "odds": settings.cache_ttl_odds,
        }
        self._client: APIFootballClient | None = None

    # ── lifecycle ───────────────────────────────────────────────────── #
    @property
    def client(self) -> APIFootballClient:
        if self._client is None:
            raise ProviderConfigurationError(
                "APIFootballProvider client not initialized. Call connect() first."
            )
        return self._client

    async def connect(self) -> None:
        self._client = APIFootballClient(
            api_key=self.api_key or get_settings().api_football_key,
            base_url=get_settings().api_football_base_url,
        )

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> APIFootballProvider:
        await self.connect()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()

    # ── caching helpers ─────────────────────────────────────────────── #
    def _cache_key(self, namespace: str, *parts: Any) -> str:
        raw = "|".join(str(p) for p in parts)
        digest = hashlib.md5(raw.encode("utf-8")).hexdigest()
        return f"af:{namespace}:{digest}"

    async def _get_cached(self, namespace: str, *parts: Any) -> Any | None:
        if self.cache is None:
            return None
        key = self._cache_key(namespace, *parts)
        try:
            return await self.cache.get_json(key)
        except Exception:
            logger.debug("Cache read failed", extra={"key": key})
            return None

    async def _set_cached(
        self, namespace: str, value: Any, *parts: Any, ttl: int | None = None
    ) -> None:
        if self.cache is None:
            return
        key = self._cache_key(namespace, *parts)
        try:
            await self.cache.set_json(key, value, ttl or self.ttls.get(namespace, 300))
        except Exception:
            logger.debug("Cache write failed", extra={"key": key})

    async def _clear_cached(self, namespace: str, *parts: Any) -> None:
        if self.cache is None:
            return
        key = self._cache_key(namespace, *parts)
        try:
            await self.cache.delete(key)
        except Exception:
            pass

    # ── cache invalidation ────────────────────────────────────────────── #
    async def invalidate_cache(self, namespace: str, *keys: str) -> None:
        """Invalidate cache entries for a given namespace and keys."""
        if self.cache is None:
            return
        for key in keys:
            cache_key = self._cache_key(namespace, key)
            try:
                await self.cache.delete(cache_key)
            except Exception:
                logger.debug("Cache invalidation failed", extra={"key": cache_key})
        # Also clear the main namespace cache if no specific keys provided
        if not keys:
            main_key = self._cache_key(namespace)
            try:
                await self.cache.delete(main_key)
            except Exception:
                pass

    # ── helpers ─────────────────────────────────────────────────────── #
    @staticmethod
    def _normalize_status(raw: Any) -> FixtureStatus:
        if raw is None:
            return FixtureStatus.SCHEDULED
        raw_str = str(raw).lower().strip()
        mapping: dict[str, FixtureStatus] = {
            "int": FixtureStatus.LIVE,
            "live": FixtureStatus.LIVE,
            "halftime": FixtureStatus.LIVE,
            "fulltime": FixtureStatus.FINISHED,
            "finished": FixtureStatus.FINISHED,
            "postponed": FixtureStatus.POSTPONED,
            "suspended": FixtureStatus.SUSPENDED,
            "cancelled": FixtureStatus.CANCELLED,
            "awarded": FixtureStatus.AWARDED,
            "abandoned": FixtureStatus.ABANDONED,
        }
        short = raw_str.replace(" ", "_")
        return mapping.get(short, FixtureStatus.SCHEDULED)

    @staticmethod
    def _normalize_severity(raw: Any) -> InjurySeverity | None:
        if raw is None:
            return None
        raw_str = str(raw).lower().strip()
        if raw_str in ("doubtful", "questionable"):
            return InjurySeverity.LOW
        if raw_str in ("unlikely",):
            return InjurySeverity.MEDIUM
        if raw_str in ("out", "doubtful", "injured"):
            return InjurySeverity.UNAVAILABLE
        return InjurySeverity.MEDIUM

    @staticmethod
    def _parse_timestamp(ts: Any) -> datetime | None:
        if ts is None:
            return None
        if isinstance(ts, datetime):
            return ts
        try:
            if isinstance(ts, int):
                return datetime.fromtimestamp(ts, tz=UTC)
            return datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None

    # ── leagues & seasons ───────────────────────────────────────────── #
    async def get_leagues(self, **kwargs: Any) -> list[NormalizedLeague]:
        cached = await self._get_cached("leagues")
        if cached is not None:
            return [NormalizedLeague(**item) if isinstance(item, dict) else item for item in cached]

        data = await self.client.get_leagues()
        leagues = [self._normalize_league(entry) for entry in data]
        serializable = [entry.model_dump(mode="json") for entry in leagues]
        await self._set_cached("leagues", serializable)
        return leagues

    async def get_league(self, league_id: str, **kwargs: Any) -> NormalizedLeague | None:
        cached = await self._get_cached("leagues", league_id)
        if cached is not None:
            return NormalizedLeague(**cached)

        data = await self.client.get_league(league_id)
        if not data:
            return None
        league = self._normalize_league(data[0])
        await self._set_cached("leagues", league.model_dump(mode="json"), league_id)
        return league

    async def get_seasons(
        self, league_id: str | None = None, **kwargs: Any
    ) -> list[NormalizedSeason]:
        cache_parts = ("seasons", league_id or "all")
        cached = await self._get_cached(*cache_parts)
        if cached is not None:
            return [NormalizedSeason(**item) for item in cached]

        data = await self.client.get_seasons(league_id)
        seasons = [self._normalize_season(entry, league_id) for entry in data]
        await self._set_cached(
            "seasons", [s.model_dump(mode="json") for s in seasons], *cache_parts
        )
        return seasons

    async def get_league_season(
        self, league_id: str, season_id: str, **kwargs: Any
    ) -> NormalizedSeason | None:
        seasons = await self.get_seasons(league_id)
        for s in seasons:
            if s.provider_season_id == str(season_id):
                return s
        return None

    # ── teams ───────────────────────────────────────────────────────── #
    async def get_teams(
        self,
        league_id: str | None = None,
        season_id: str | None = None,
        **kwargs: Any,
    ) -> list[NormalizedTeam]:
        cache_key_parts = ("teams", league_id or "", season_id or "")
        cached = await self._get_cached(*cache_key_parts)
        if cached is not None:
            return [NormalizedTeam(**item) for item in cached]

        data = await self.client.get_teams(league_id=league_id, season_id=season_id)
        teams = [self._normalize_team(entry) for entry in data]
        await self._set_cached(
            "teams",
            [t.model_dump(mode="json") for t in teams],
            *cache_key_parts,
        )
        return teams

    async def get_team(self, team_id: str, **kwargs: Any) -> NormalizedTeam | None:
        cached = await self._get_cached("teams", "single", team_id)
        if cached is not None:
            return NormalizedTeam(**cached)

        data = await self.client.get_team(team_id)
        if not data:
            return None
        team = self._normalize_team(data[0])
        await self._set_cached("teams", team.model_dump(mode="json"), "single", team_id)
        return team

    # ── team statistics ─────────────────────────────────────────────── #
    async def get_team_statistics(
        self,
        team_id: str,
        league_id: str | None = None,
        season_id: str | None = None,
        **kwargs: Any,
    ) -> NormalizedTeamStatistics | None:
        cache_key_parts = ("statistics", team_id, league_id or "", season_id or "")
        cached = await self._get_cached(*cache_key_parts)
        if cached is not None:
            return NormalizedTeamStatistics(**cached)

        params: dict[str, Any] = {"team": team_id}
        if league_id:
            params["league"] = league_id
        if season_id:
            params["season"] = season_id
        data = await self.client.request_all_pages("/teams/statistics", params=params)
        if not data:
            return None
        stats = self._normalize_team_statistics(data[0], team_id)
        await self._set_cached("statistics", stats.model_dump(mode="json"), *cache_key_parts)
        return stats

    async def get_team_form(
        self, team_id: str, fixture_id: str | None = None, **kwargs: Any
    ) -> NormalizedForm | None:
        cache_key_parts = ("form", team_id, fixture_id or "current")
        cached = await self._get_cached(*cache_key_parts)
        if cached is not None:
            return NormalizedForm(**cached)

        last_n = kwargs.get("last_n", get_settings().sync_form_match_count)
        fixtures = await self.get_fixtures(team_id=team_id, last_n=last_n)
        if not fixtures:
            return None
        form = self._calculate_form(fixtures, team_id)
        await self._set_cached("form", form.model_dump(mode="json"), *cache_key_parts)
        return form

    @staticmethod
    def _calculate_form(fixtures: list[NormalizedFixture], team_id: str) -> NormalizedForm:
        """Compute form metrics from recent fixtures for a given team."""
        wins = draws = losses = 0
        goals_scored = goals_conceded = 0
        clean_sheets = failed_to_score = 0

        for f in fixtures:
            if not f.is_finished or (f.home_score is None) or (f.away_score is None):
                continue
            if f.home_team_id == team_id:
                gs, gc = f.home_score, f.away_score
            elif f.away_team_id == team_id:
                gs, gc = f.away_score, f.home_score
            else:
                continue

            goals_scored += gs
            goals_conceded += gc
            if gs > gc:
                wins += 1
            elif gs == gc:
                draws += 1
            else:
                losses += 1
            if gc == 0:
                clean_sheets += 1
            if gs == 0:
                failed_to_score += 1

        total = wins + draws + losses
        return NormalizedForm(
            provider="api_football",
            provider_team_id=team_id,
            recent_matches=fixtures,
            wins=wins,
            draws=draws,
            losses=losses,
            goals_scored=goals_scored,
            goals_conceded=goals_conceded,
            points_per_match=(wins * 3 + draws) / total if total else 0.0,
            average_goals_scored=goals_scored / total if total else 0.0,
            average_goals_conceded=goals_conceded / total if total else 0.0,
            clean_sheet_rate=clean_sheets / total if total else 0.0,
            failed_to_score_rate=failed_to_score / total if total else 0.0,
        )

    # ── fixtures ────────────────────────────────────────────────────── #
    async def get_fixtures(
        self,
        league_id: str | None = None,
        season_id: str | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        team_id: str | None = None,
        **kwargs: Any,
    ) -> list[NormalizedFixture]:
        params: dict[str, Any] = {}
        if league_id:
            params["league"] = league_id
        if season_id:
            params["season"] = season_id
        if from_date:
            params["from"] = from_date.strftime("%Y-%m-%d")
        if to_date:
            params["to"] = to_date.strftime("%Y-%m-%d")
        if team_id:
            params["team"] = team_id
        if kwargs.get("last_n"):
            params["last"] = str(kwargs["last_n"])
        if kwargs.get("status"):
            params["status"] = kwargs["status"]

        cache_key_parts = ("fixtures", str(params))
        cached = await self._get_cached(*cache_key_parts)
        if cached is not None:
            return [NormalizedFixture(**item) for item in cached]

        data = await self.client.get_fixtures(params=params)
        fixtures = [self._normalize_fixture(entry) for entry in data]
        await self._set_cached(
            "fixtures", [f.model_dump(mode="json") for f in fixtures], *cache_key_parts
        )
        return fixtures

    async def get_fixture(self, fixture_id: str, **kwargs: Any) -> NormalizedFixture | None:
        cached = await self._get_cached("fixtures", "single", fixture_id)
        if cached is not None:
            return NormalizedFixture(**cached)

        data = await self.client.get_fixture(fixture_id)
        if not data:
            return None
        fixture = self._normalize_fixture(data[0])
        await self._set_cached("fixtures", fixture.model_dump(mode="json"), "single", fixture_id)
        return fixture

    # ── head-to-head ────────────────────────────────────────────────── #
    async def get_head_to_head(
        self, team_a_id: str, team_b_id: str, league_id: str | None = None, **kwargs: Any
    ) -> NormalizedHeadToHead | None:
        cache_key_parts = ("h2h", team_a_id, team_b_id, league_id or "all")
        cached = await self._get_cached(*cache_key_parts)
        if cached is not None:
            return NormalizedHeadToHead(**cached)

        params: dict[str, Any] = {"id": team_a_id, "vs": team_b_id}
        if league_id:
            params["league"] = league_id
        data = await self.client.request_all_pages(
            "/fixtures/headtoh2h" if False else "/fixtures/headtoh2h", params=params
        )
        fixtures = [self._normalize_fixture(e) for e in data]
        if not fixtures:
            return None
        h2h = self._build_h2h(fixtures, team_a_id, team_b_id, league_id)
        await self._set_cached("form", h2h.model_dump(mode="json"), *cache_key_parts)
        return h2h

    @staticmethod
    def _build_h2h(
        fixtures: list[NormalizedFixture],
        team_a_id: str,
        team_b_id: str,
        league_id: str | None,
    ) -> NormalizedHeadToHead:
        team_a_wins = sum(
            1
            for f in fixtures
            if f.is_finished
            and f.home_team_id == team_a_id
            and (f.home_score or 0) > (f.away_score or 0)
        )
        team_b_wins = sum(
            1
            for f in fixtures
            if f.is_finished
            and f.home_team_id == team_a_id
            and (f.away_score or 0) > (f.home_score or 0)
        )
        draws = sum(
            1 for f in fixtures if f.is_finished and (f.home_score or 0) == (f.away_score or 0)
        )
        return NormalizedHeadToHead(
            provider="api_football",
            team_a_id=team_a_id,
            team_b_id=team_b_id,
            league_id=league_id,
            fixtures=fixtures,
            team_a_wins=team_a_wins,
            team_b_wins=team_b_wins,
            draws=draws,
        )

    # ── injuries & suspensions ──────────────────────────────────────── #
    async def get_injuries(
        self, team_id: str | None = None, fixture_id: str | None = None, **kwargs: Any
    ) -> list[NormalizedInjury]:
        params: dict[str, Any] = {}
        if team_id:
            params["team"] = team_id
        if fixture_id:
            params["fixture"] = fixture_id
        cache_key_parts = ("injuries", team_id or "", fixture_id or "")
        cached = await self._get_cached(*cache_key_parts)
        if cached is not None:
            return [NormalizedInjury(**item) for item in cached]

        data = (
            await self.client.get_injuries(params=params)
            if params
            else await self.client.get_injuries()
        )
        injuries = [self._normalize_injury(entry) for entry in data]
        await self._set_cached(
            "injuries", [i.model_dump(mode="json") for i in injuries], *cache_key_parts
        )
        return injuries

    async def get_suspensions(
        self, team_id: str | None = None, fixture_id: str | None = None, **kwargs: Any
    ) -> list[NormalizedSuspension]:
        # API-Football does not have a dedicated suspensions endpoint.
        # Sidelined players can be fetched from the /sidelined endpoint.
        params: dict[str, Any] = {}
        if team_id:
            params["team"] = team_id
        if fixture_id:
            params["fixture"] = fixture_id
        data = (
            await self.client.get_sidelined(params=params)
            if params
            else await self.client.get_sidelined()
        )
        return [self._normalize_suspension(entry) for entry in data]

    # ── lineups ─────────────────────────────────────────────────────── #
    async def get_lineups(
        self, fixture_id: str, **kwargs: Any
    ) -> dict[str, NormalizedLineup] | list[NormalizedLineup]:
        cached = await self._get_cached("lineups", fixture_id)
        if cached is not None:
            result: dict[str, NormalizedLineup] = {}
            for key, val in cached.items():
                result[key] = NormalizedLineup(**val)
            return result

        data = await self.client.get_lineups(fixture_id)
        result: dict[str, NormalizedLineup] = {}
        for entry in data:
            lineup = self._normalize_lineup(entry)
            if lineup is not None:
                key = lineup.team_id or lineup.team_name or "unknown"
                result[key] = lineup
        serializable = {k: v.model_dump(mode="json") for k, v in result.items()}
        await self._set_cached("lineups", serializable, fixture_id)
        return result

    async def get_predicted_lineups(
        self, fixture_id: str, **kwargs: Any
    ) -> NormalizedLineup | None:
        # API-Football does not expose a predicted-lineups endpoint directly.
        return None

    # ── match statistics ────────────────────────────────────────────── #
    async def get_match_statistics(
        self, fixture_id: str, **kwargs: Any
    ) -> NormalizedMatchStatistics | None:
        cached = await self._get_cached("statistics", fixture_id)
        if cached is not None:
            return NormalizedMatchStatistics(**cached)

        data = await self.client.get_match_statistics(fixture_id)
        if not data:
            return None
        stats = self._normalize_match_statistics(data, fixture_id)
        await self._set_cached("statistics", stats.model_dump(mode="json"), fixture_id)
        return stats

    # ── odds ────────────────────────────────────────────────────────── #
    async def get_odds(self, fixture_id: str | None = None, **kwargs: Any) -> NormalizedOdds | None:
        if not fixture_id:
            return None
        cached = await self._get_cached("odds", fixture_id)
        if cached is not None:
            return NormalizedOdds(**cached)

        data = await self.client.get_odds(fixture_id)
        if not data:
            return None
        odds = self._normalize_odds(data, fixture_id)
        await self._set_cached("odds", odds.model_dump(mode="json"), fixture_id)
        return odds

    # ── players ─────────────────────────────────────────────────────── #
    async def get_players(
        self, team_id: str | None = None, **kwargs: Any
    ) -> list[NormalizedPlayer]:
        params: dict[str, Any] = {}
        if team_id:
            params["team"] = team_id
        if kwargs.get("season_id"):
            params["season"] = kwargs["season_id"]
        data = await self.client.get_players(params=params)
        return [self._normalize_player(entry, kwargs.get("season_id")) for entry in data]

    async def get_standings(
        self,
        league_id: str | None = None,
        season_id: str | None = None,
        **kwargs: Any,
    ) -> NormalizedStandings | None:
        params: dict[str, Any] = {}
        if league_id:
            params["league"] = league_id
        if season_id:
            params["season"] = season_id
        data = await self.client.get_standings(params=params)
        standings: list[NormalizedStanding] = []
        for entry in data:
            league_info = entry.get("league", {})
            standings_list = league_info.get("standings", [])
            for group in standings_list:
                for row in group:
                    standings.append(self._normalize_standing(row))
        return NormalizedStandings(
            provider=self.provider_name,
            league_id=league_id,
            season_id=season_id,
            standings=standings,
        )

    async def get_timezones(self, **kwargs: Any) -> list[str]:
        params = kwargs.get("params") if isinstance(kwargs.get("params"), dict) else None
        data = await self.client.get_timezones(params=params)
        return [item.get("timezone", str(item)) for item in data if isinstance(item, dict)]

    async def get_countries(self, **kwargs: Any) -> list[dict[str, Any]]:
        params = kwargs.get("params") if isinstance(kwargs.get("params"), dict) else None
        return await self.client.get_countries(params=params)

    async def get_venues(
        self, venue_id: str | None = None, team_id: str | None = None, **kwargs: Any
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if venue_id:
            params["id"] = venue_id
        if team_id:
            params["team"] = team_id
        return await self.client.get_venues(params=params)

    async def get_coaches(
        self, team_id: str | None = None, coach_id: str | None = None, **kwargs: Any
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if team_id:
            params["team"] = team_id
        if coach_id:
            params["id"] = coach_id
        return await self.client.get_coaches(params=params)

    async def get_transfers(
        self, player_id: str | None = None, team_id: str | None = None, **kwargs: Any
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if player_id:
            params["player"] = player_id
        if team_id:
            params["team"] = team_id
        return await self.client.get_transfers(params=params)

    async def get_trophies(
        self, player_id: str | None = None, team_id: str | None = None, **kwargs: Any
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if player_id:
            params["player"] = player_id
        if team_id:
            params["team"] = team_id
        return await self.client.get_trophies(params=params)

    async def get_predictions(self, fixture_id: str, **kwargs: Any) -> list[dict[str, Any]]:
        params = kwargs.get("params") if isinstance(kwargs.get("params"), dict) else None
        return await self.client.get_predictions(fixture_id, params=params)

    async def get_sidelined(
        self, team_id: str | None = None, fixture_id: str | None = None, **kwargs: Any
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if team_id:
            params["team"] = team_id
        if fixture_id:
            params["fixture"] = fixture_id
        return await self.client.get_sidelined(params=params)

    async def get_pre_match_odds(
        self, fixture_id: str | None = None, **kwargs: Any
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = dict(kwargs)
        if fixture_id:
            params["fixture"] = fixture_id
        return await self.client.get_odds_pre_match(params=params)

    async def get_in_play_odds(
        self, fixture_id: str | None = None, **kwargs: Any
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = dict(kwargs)
        if fixture_id:
            params["fixture"] = fixture_id
        return await self.client.get_odds_live(params=params)

    # ── health check ────────────────────────────────────────────────── #
    async def health_check(self) -> bool:
        try:
            await self.connect()
            result = await self.client.health_check()
            await self.close()
            return result["healthy"]
        except Exception as exc:
            logger.warning(f"API Football health check failed: {exc}")
            return False

    # ── normalizers ─────────────────────────────────────────────────── #
    @staticmethod
    def _normalize_league(raw: dict[str, Any]) -> NormalizedLeague:
        league = raw.get("league", raw)
        country = raw.get("country") or league.get("country") or {}
        if isinstance(country, str):
            country = {"name": country}
        return NormalizedLeague(
            provider="api_football",
            provider_league_id=str(league.get("id", "")),
            name=league.get("name", ""),
            country=country.get("name") if isinstance(country, dict) else country,
            country_code=country.get("code") if isinstance(country, dict) else None,
            season_count=league.get("season_count"),
            provider_metadata={"type": league.get("type"), "logo": league.get("logo")},
        )

    @staticmethod
    def _normalize_season(raw: dict[str, Any], league_id: str | None) -> NormalizedSeason:
        return NormalizedSeason(
            provider="api_football",
            provider_season_id=str(raw.get("id", raw.get("year", ""))),
            league_id=league_id or "",
            name=str(raw.get("year", raw.get("id", ""))),
            year=raw.get("year"),
            start_date=raw.get("start"),
            end_date=raw.get("end"),
            is_current=bool(raw.get("current", False)),
            provider_metadata={"coverage": raw.get("coverage", {})},
        )

    @staticmethod
    def _normalize_team(raw: dict[str, Any]) -> NormalizedTeam:
        team = raw.get("team", raw)
        venue = raw.get("venue", {}) or {}
        return NormalizedTeam(
            provider="api_football",
            provider_team_id=str(team.get("id", "")),
            name=team.get("name", ""),
            short_name=team.get("short", team.get("code")),
            slug=team.get("slug"),
            logo_url=team.get("logo"),
            venue_name=venue.get("name"),
            venue_city=venue.get("city"),
            founded=team.get("founded"),
            country=team.get("country"),
            provider_metadata={"code": team.get("code"), "country": team.get("country")},
        )

    @staticmethod
    def _normalize_team_statistics(raw: dict[str, Any], team_id: str) -> NormalizedTeamStatistics:
        fixtures_stats = raw.get("fixtures", {}) or {}
        goals_stats = raw.get("goals", {}) or {}
        goals_for_total = goals_stats.get("for", {}).get("total", {}).get("total")
        goals_against_total = goals_stats.get("against", {}).get("total", {}).get("total")
        home_goals_for = goals_stats.get("for", {}).get("home", {}).get("total")
        away_goals_for = goals_stats.get("for", {}).get("away", {}).get("total")
        home_goals_against = goals_stats.get("against", {}).get("home", {}).get("total")
        away_goals_against = goals_stats.get("against", {}).get("away", {}).get("total")

        return NormalizedTeamStatistics(
            provider="api_football",
            provider_team_id=team_id,
            games_played=fixtures_stats.get("played", {}).get("total"),
            wins=fixtures_stats.get("wins", {}).get("total"),
            draws=fixtures_stats.get("draw", {}).get("total"),
            losses=fixtures_stats.get("lose", {}).get("total"),
            goals_for=goals_for_total,
            goals_against=goals_against_total,
            home_goals_for=home_goals_for,
            away_goals_for=away_goals_for,
            home_goals_against=home_goals_against,
            away_goals_against=away_goals_against,
            clean_sheets=raw.get("clean_sheet", {}).get("total"),
            failed_to_score=raw.get("failed_to_score", {}).get("total"),
            points=raw.get("points"),
            position=raw.get("position"),
            average_possession=_to_float(raw.get("possession", {}).get("average")),
            average_shots=_to_float(raw.get("shots", {}).get("average", {}).get("total")),
            average_shots_on_target=_to_float(
                raw.get("shots_on_target", {}).get("average", {}).get("total")
            ),
            average_xg=_to_float(raw.get("expected_goals", {}).get("average")),
            average_xga=_to_float(raw.get("expected_goals_against", {}).get("average")),
            goals_per_game=_to_float(goals_stats.get("for", {}).get("average", {}).get("total")),
            goals_conceded_per_game=_to_float(
                goals_stats.get("against", {}).get("average", {}).get("total")
            ),
            provider_metadata={"league": raw.get("league", {}), "form": raw.get("form", {})},
        )

    @staticmethod
    def _normalize_fixture(raw: dict[str, Any]) -> NormalizedFixture:
        fixture = raw.get("fixture", raw)
        teams = raw.get("teams", {})
        goals = raw.get("goals", {})
        league = raw.get("league", {})
        score = raw.get("score", {})
        kickoff_at = APIFootballProvider._parse_timestamp(fixture.get("timestamp"))
        status_raw = fixture.get("status", {}).get("short")
        status = APIFootballProvider._normalize_status(status_raw)
        return NormalizedFixture(
            provider="api_football",
            provider_fixture_id=str(fixture.get("id", "")),
            league_id=str(league.get("id", "")) if league else None,
            provider_league_id=str(league.get("id", "")) if league else None,
            season_id=str(league.get("season", "")) if league else None,
            provider_season_id=str(league.get("season", "")) if league else None,
            home_team_id=str(teams.get("home", {}).get("id", ""))
            if isinstance(teams, dict)
            else None,
            provider_home_team_id=str(teams.get("home", {}).get("id", ""))
            if isinstance(teams, dict)
            else None,
            away_team_id=str(teams.get("away", {}).get("id", ""))
            if isinstance(teams, dict)
            else None,
            provider_away_team_id=str(teams.get("away", {}).get("id", ""))
            if isinstance(teams, dict)
            else None,
            home_team_name=teams.get("home", {}).get("name") if isinstance(teams, dict) else None,
            away_team_name=teams.get("away", {}).get("name") if isinstance(teams, dict) else None,
            kickoff_at=kickoff_at,
            timezone=fixture.get("timezone"),
            status=status,
            venue=fixture.get("venue", {}).get("name"),
            referee=fixture.get("referee"),
            home_score=goals.get("home") if isinstance(goals, dict) else None,
            away_score=goals.get("away") if isinstance(goals, dict) else None,
            halftime_home_score=score.get("halftime", {}).get("home")
            if isinstance(score, dict)
            else None,
            halftime_away_score=score.get("halftime", {}).get("away")
            if isinstance(score, dict)
            else None,
            fulltime_home_score=score.get("fulltime", {}).get("home")
            if isinstance(score, dict)
            else None,
            fulltime_away_score=score.get("fulltime", {}).get("away")
            if isinstance(score, dict)
            else None,
            is_finished=status == FixtureStatus.FINISHED,
            provider_metadata={
                "league_name": league.get("name") if league else None,
                "round": league.get("round") if league else None,
                "venue_city": fixture.get("venue", {}).get("city"),
                "status_long": fixture.get("status", {}).get("long"),
            },
        )

    @staticmethod
    def _normalize_injury(raw: dict[str, Any]) -> NormalizedInjury:
        player = raw.get("player", {}) or {}
        team = raw.get("team", {}) or {}
        return NormalizedInjury(
            provider="api_football",
            provider_player_id=str(player.get("id", "")) if player else None,
            provider_team_id=str(team.get("id", "")) if team else None,
            team_id=str(team.get("id", "")) if team else None,
            player_name=player.get("name", ""),
            position=player.get("position"),
            injury_type=raw.get("type", raw.get("injury", {}).get("type")),
            severity=APIFootballProvider._normalize_severity(raw.get("severity")),
            description=raw.get("description"),
            start_date=APIFootballProvider._parse_timestamp(raw.get("date")),
            return_date=APIFootballProvider._parse_timestamp(raw.get("return_date")),
            is_startingXI_impact=bool(raw.get("player", {}).get("id")),
            provider_metadata={
                "reason": player.get("reason"),
                "team_name": team.get("name"),
                "fixture_id": raw.get("fixture", {}).get("id")
                if isinstance(raw.get("fixture"), dict)
                else None,
            },
        )

    @staticmethod
    def _normalize_suspension(raw: dict[str, Any]) -> NormalizedSuspension:
        player = raw.get("player", {}) or {}
        team = raw.get("team", {}) or {}
        return NormalizedSuspension(
            provider="api_football",
            provider_player_id=str(player.get("id", "")) if player else None,
            provider_team_id=str(team.get("id", "")) if team else None,
            team_id=str(team.get("id", "")) if team else None,
            player_name=player.get("name", ""),
            position=player.get("position"),
            reason=raw.get("reason", raw.get("type")),
            suspension_type=raw.get("suspension_type", raw.get("type")),
            suspended_from=APIFootballProvider._parse_timestamp(raw.get("start_date")),
            suspended_until=APIFootballProvider._parse_timestamp(raw.get("end_date")),
            provider_metadata={
                "team_name": team.get("name"),
                "injury_type": raw.get("injury_type"),
            },
        )

    @staticmethod
    def _normalize_lineup(raw: dict[str, Any]) -> NormalizedLineup | None:
        if not raw:
            return None
        team = raw.get("team", {}) or {}
        formation_obj = raw.get("formation", {}) or {}
        formation = formation_obj.get("formation")
        lineup_list = formation_obj.get("lineup", []) or []
        subs_list = raw.get("substitutes", {}).get("substitutes", []) or []

        starting_xi = [
            NormalizedLineupPlayer(
                player_name=p.get("player", {}).get("name", "")
                if isinstance(p, dict)
                else str(p.get("name", p)),
                position=p.get("pos") if isinstance(p, dict) else None,
                jersey_number=p.get("jersey") if isinstance(p, dict) else None,
                is_starter=True,
                is_substitute=False,
            )
            for p in lineup_list
        ]
        substitutes = [
            NormalizedLineupPlayer(
                player_name=s.get("player", {}).get("name", "")
                if isinstance(s, dict)
                else str(s.get("name", s)),
                position=s.get("pos") if isinstance(s, dict) else None,
                jersey_number=s.get("jersey") if isinstance(s, dict) else None,
                is_starter=False,
                is_substitute=True,
            )
            for s in subs_list
        ]
        return NormalizedLineup(
            provider="api_football",
            provider_fixture_id=str(raw.get("fixture", {}).get("id", "")),
            team_id=str(team.get("id", "")),
            team_name=team.get("name"),
            status=LineupStatus.CONFIRMED,
            formation=formation,
            players=starting_xi + substitutes,
            starting_xi=starting_xi,
            substitutes=substitutes,
        )

    @staticmethod
    def _normalize_match_statistics(
        raw_list: list[dict[str, Any]], fixture_id: str
    ) -> NormalizedMatchStatistics:
        home_stats: dict[str, Any] = {}
        away_stats: dict[str, Any] = {}
        for entry in raw_list:
            team_obj = entry.get("team", {})
            if isinstance(team_obj, dict) and "home" in team_obj.get("name", "").lower():
                home_stats = entry
            elif not home_stats:
                home_stats = entry
            else:
                away_stats = entry
        return NormalizedMatchStatistics(
            provider="api_football",
            provider_fixture_id=fixture_id,
            home_team_id=str(home_stats.get("team", {}).get("id", "")) if home_stats else None,
            away_team_id=str(away_stats.get("team", {}).get("id", "")) if away_stats else None,
            possession={
                "home": _to_float(_extract_stat(home_stats, "Ball Possession")),
                "away": _to_float(_extract_stat(away_stats, "Ball Possession")),
            },
            shots={
                "home": _to_int(_extract_stat(home_stats, "Total Shots")),
                "away": _to_int(_extract_stat(away_stats, "Total Shots")),
            },
            shots_on_target={
                "home": _to_int(_extract_stat(home_stats, "Shots on Goal")),
                "away": _to_int(_extract_stat(away_stats, "Shots on Goal")),
            },
            xg={
                "home": _to_float(_extract_stat(home_stats, "Expected Goals")),
                "away": _to_float(_extract_stat(away_stats, "Expected Goals")),
            },
            corners={
                "home": _to_int(_extract_stat(home_stats, "Corner Kicks")),
                "away": _to_int(_extract_stat(away_stats, "Corner Kicks")),
            },
            is_finished=True,
            provider_metadata={"raw": raw_list},
        )

    @staticmethod
    def _normalize_player(raw: dict[str, Any], season_id: str | None = None) -> NormalizedPlayer:
        team = raw.get("team", {}) or {}
        player_data = raw.get("player", raw) or {}
        return NormalizedPlayer(
            provider="api_football",
            provider_player_id=str(player_data.get("id", "")),
            team_id=str(team.get("id", "")) if team else None,
            first_name=player_data.get("firstname"),
            last_name=player_data.get("lastname"),
            full_name=player_data.get("name", ""),
            position=player_data.get("position"),
            date_of_birth=_parse_date(player_data.get("birth", {}).get("date"))
            if isinstance(player_data.get("birth"), dict)
            else None,
            nationality=player_data.get("nationality"),
            height=player_data.get("height"),
            weight=player_data.get("weight"),
            provider_metadata={"team_name": team.get("name"), "season_id": season_id},
        )

    @staticmethod
    def _normalize_standing(raw: dict[str, Any]) -> NormalizedStanding:
        games = raw.get("games", {}) or {}
        wins = (
            games.get("win", {}).get("total")
            if isinstance(games.get("win"), dict)
            else games.get("win")
        )
        draws = (
            games.get("draw", {}).get("total")
            if isinstance(games.get("draw"), dict)
            else games.get("draw")
        )
        losses = (
            games.get("lose", {}).get("total")
            if isinstance(games.get("lose"), dict)
            else games.get("lose")
        )
        goals = raw.get("goals", {}) or {}
        gf = goals.get("for", 0)
        ga = goals.get("against", 0)
        return NormalizedStanding(
            team_id=str(raw.get("team", {}).get("id", "")),
            team_name=raw.get("team", {}).get("name", ""),
            position=raw.get("rank", 0),
            points=raw.get("points", 0),
            played=games.get("played", 0),
            wins=wins or 0,
            draws=draws or 0,
            losses=losses or 0,
            goals_for=gf,
            goals_against=ga,
            goal_difference=gf - ga,
            form=raw.get("form"),
            provider_metadata={"group": raw.get("group"), "status": raw.get("status")},
        )

    @staticmethod
    def _normalize_odds(raw_list: list[dict[str, Any]], fixture_id: str) -> NormalizedOdds:
        markets: list[NormalizedOddsMarket] = []
        for bookmaker_entry in raw_list:
            bookmaker_name = bookmaker_entry.get("bookmaker", {}).get("name", "")
            for odds_entry in (
                bookmaker_entry.get("bookmakers", []) if isinstance(bookmaker_entry, dict) else []
            ):
                bk_name = odds_entry.get("name", bookmaker_name)
                for market in odds_entry.get("markets", []):
                    market_name = market.get("name", "")
                    for selection in market.get("selections", []):
                        price = _to_float(selection.get("price"))
                        if price is None:
                            continue
                        implied = 1.0 / price if price > 0 else None
                        markets.append(
                            NormalizedOddsMarket(
                                market=market_name,
                                selection=selection.get("name", ""),
                                odds=price,
                                is_main=True,
                                provider_metadata={
                                    "bookmaker": bk_name,
                                    "implied_probability": implied,
                                    "handicap": selection.get("handicap"),
                                },
                            )
                        )
        return NormalizedOdds(
            provider="api_football",
            provider_fixture_id=fixture_id,
            markets=markets,
        )


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _extract_stat(stats_dict: dict[str, Any], label: str) -> Any:
    """Extract a stat by its display label from API-Football statistics response."""
    if not stats_dict:
        return None
    for item in stats_dict.get("statistics", []):
        if item.get("name", "").lower().replace(" ", "_") == label.lower().replace(" ", "_"):
            return item.get("value")
    return None


def _parse_date(value: Any) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None

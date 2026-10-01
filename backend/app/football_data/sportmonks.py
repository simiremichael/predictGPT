"""Sportmonks provider implementation.

Implements the same ``FootballDataProvider`` interface as the API-Football
provider but talks to the Sportmonks v3 API, normalizing all responses into
the identical ``Normalized*`` internal models.

Configuration:
    SPORTMONKS_API_TOKEN -- API token (read from env, never hardcoded)
    SPORTMONKS_BASE_URL  -- default https://api.sportmonks.com/v3/football

Sportmonks passes the token as a ``token`` query parameter.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from core.config import get_settings
from core.exceptions import (
    ProviderConfigurationError,
    ProviderNotFoundError,
)
from football_data.base import FootballDataProvider
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
from football_data.sportmonks_client import SportmonksClient

logger = logging.getLogger(__name__)

# Sportmonks league id -> internal id (replace with authoritative IDs).
# These placeholders preserve the correct architecture; real Sportmonks
# v3 league/season IDs should be filled in below when the token is active.
_DEFAULT_LEAGUE_IDS_SPORTMONKS: dict[str, tuple[str, str]] = {
    "premier_league": ("39", "2023"),
    "championship": ("40", "2023"),
    "league_one": ("41", "2023"),
    "la_liga": ("140", "2023"),
    "segunda_division": ("141", "2023"),
    "serie_a": ("135", "2023"),
    "serie_b": ("136", "2023"),
    "bundesliga": ("78", "2023"),
    "bundesliga_2": ("79", "2023"),
    "ligue_1": ("61", "2023"),
    "ligue_2": ("62", "2023"),
    "primeira_liga": ("144", "2023"),
    "liga_portugal_2": ("145", "2023"),
    "super_lig": ("40", "2023"),
    "tff_1_lig": ("41", "2023"),
    "super_league": ("211", "2023"),
    "football_league": ("212", "2023"),
    "swiss_super_league": ("75", "2023"),
    "challenge_league": ("76", "2023"),
    "eredivisie": ("88", "2023"),
    "eerste_divisie": ("190", "2023"),
    "jupiler_pro_league": ("144", "2023"),
    "challenger_pro_league": ("145", "2023"),
    "champions_league": ("2", "2023"),
    "europa_league": ("3", "2023"),
    "conference_league": ("4", "2023"),
}


def _register_sportmonks_league_ids() -> None:
    from football_data.league_mappings import LeagueMapping

    for internal_id, (league_id, season_id) in _DEFAULT_LEAGUE_IDS_SPORTMONKS.items():
        cfg = LeagueMapping.get(internal_id)
        if cfg is not None:
            cfg.add_provider("sportmonks", league_id, season_id)  # type: ignore[arg-type]


_register_sportmonks_league_ids()


class SportmonksProvider(FootballDataProvider):
    """Concrete provider for the Sportmonks v3 football API."""

    provider_name = "sportmonks"

    def __init__(
        self,
        api_token: str | None = None,
        base_url: str | None = None,
    ) -> None:
        if not api_token:
            # Try loading from settings
            settings = get_settings()
            api_token = settings.sportmonks_api_token
        if not api_token:
            raise ProviderConfigurationError(
                "SPORTMONKS_API_TOKEN is required for SportmonksProvider."
            )
        self.http = SportmonksClient(
            api_token=api_token,
            base_url=base_url,
            enabled=True,
        )

    # ── lifecycle ───────────────────────────────────────────────────── #
    async def connect(self) -> None:
        await self.http.http._ensure_client()

    async def close(self) -> None:
        await self.http.aclose()

    async def __aenter__(self) -> SportmonksProvider:
        await self.connect()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()

    # ── helpers ─────────────────────────────────────────────────────── #

    @staticmethod
    def _normalize_status(raw: Any) -> FixtureStatus:
        if raw is None:
            return FixtureStatus.SCHEDULED
        raw_str = str(raw).lower().strip()
        mapping: dict[str, FixtureStatus] = {
            "scheduled": FixtureStatus.SCHEDULED,
            "timer_started": FixtureStatus.LIVE,
            "first_half": FixtureStatus.LIVE,
            "halftime": FixtureStatus.LIVE,
            "second_half": FixtureStatus.LIVE,
            "extra_time": FixtureStatus.LIVE,
            "finished": FixtureStatus.FINISHED,
            "ended": FixtureStatus.FINISHED,
            "postponed": FixtureStatus.POSTPONED,
            "suspended": FixtureStatus.SUSPENDED,
            "cancelled": FixtureStatus.CANCELLED,
            "abandoned": FixtureStatus.ABANDONED,
        }
        return mapping.get(raw_str, FixtureStatus.SCHEDULED)

    @staticmethod
    def _normalize_severity(raw: Any) -> InjurySeverity | None:
        if raw is None:
            return None
        raw_str = str(raw).lower().strip()
        if raw_str in ("doubtful", "risk"):
            return InjurySeverity.LOW
        if raw_str in ("unlikely", "questionable"):
            return InjurySeverity.MEDIUM
        if raw_str in ("out", "ruled_out", "injured", "doubtful"):
            return InjurySeverity.UNAVAILABLE
        return InjurySeverity.MEDIUM

    # ── leagues & seasons ───────────────────────────────────────────── #
    async def get_leagues(self, **kwargs: Any) -> list[NormalizedLeague]:
        includes = kwargs.get("includes", kwargs.get("include"))
        response = await self.http.get_leagues(includes=includes)
        if not isinstance(response, list):
            response = []
        return [self._normalize_league(entry) for entry in response]

    async def get_league(self, league_id: str, **kwargs: Any) -> NormalizedLeague | None:
        includes = kwargs.get("includes", kwargs.get("include"))
        response = await self.http.get_league(league_id, includes=includes)
        if not response:
            return None
        if isinstance(response, list):
            response = response[0]
        return self._normalize_league(response)

    async def get_seasons(
        self, league_id: str | None = None, **kwargs: Any
    ) -> list[NormalizedSeason]:
        response = await self.http.get_seasons(league_id=league_id)
        if not isinstance(response, list):
            response = []
        return [self._normalize_season(entry, league_id) for entry in response]

    # ── teams ───────────────────────────────────────────────────────── #
    async def get_teams(
        self,
        league_id: str | None = None,
        season_id: str | None = None,
        **kwargs: Any,
    ) -> list[NormalizedTeam]:
        includes = kwargs.get("includes", kwargs.get("include"))
        response = await self.http.get_teams(
            league_id=league_id, season_id=season_id, includes=includes
        )
        if not isinstance(response, list):
            response = []
        return [
            self._normalize_team(entry, league_id=league_id, season_id=season_id)
            for entry in response
        ]

    async def get_team(self, team_id: str, **kwargs: Any) -> NormalizedTeam | None:
        includes = kwargs.get("includes", kwargs.get("include"))
        response = await self.http.get_team(team_id, includes=includes)
        if not response:
            return None
        if isinstance(response, list):
            response = response[0]
        return self._normalize_team(response)

    # ── team statistics ─────────────────────────────────────────────── #
    async def get_team_statistics(
        self,
        team_id: str,
        league_id: str | None = None,
        season_id: str | None = None,
        **kwargs: Any,
    ) -> NormalizedTeamStatistics | None:
        response = await self.http.get_team_statistics(team_id, season_id=season_id)
        if not response:
            return None
        if isinstance(response, list):
            response = response[0]
        return self._normalize_team_statistics(response, team_id)

    async def get_team_form(
        self, team_id: str, fixture_id: str | None = None, **kwargs: Any
    ) -> NormalizedForm | None:
        fixtures = await self.get_fixtures(team_id=team_id, last_n=5)
        if not fixtures:
            return None
        return NormalizedForm(
            provider=self.provider_name,
            provider_team_id=team_id,
            fixture_id=fixture_id,
            recent_matches=fixtures,
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
            params["league_id"] = league_id
        if season_id:
            params["season_id"] = season_id
        if from_date:
            params["from"] = from_date.strftime("%Y-%m-%d")
        if to_date:
            params["to"] = to_date.strftime("%Y-%m-%d")
        if team_id:
            params["team_id"] = team_id
        if kwargs.get("last_n"):
            params["last"] = str(kwargs["last_n"])
        if kwargs.get("today"):
            today = datetime.utcnow().date()
            params["from"] = today.strftime("%Y-%m-%d")
            params["to"] = today.strftime("%Y-%m-%d")
        if kwargs.get("upcoming"):
            params["from"] = datetime.utcnow().strftime("%Y-%m-%d")
            days = kwargs.get("days", 7)
            params["to"] = (datetime.utcnow() + timedelta(days=days)).strftime("%Y-%m-%d")

        response = await self.http.get_fixtures(
            params=params,
            includes=["participants"],
        )
        if not isinstance(response, list):
            response = []
        return [self._normalize_fixture(entry) for entry in response]

    async def get_fixture(self, fixture_id: str, **kwargs: Any) -> NormalizedFixture | None:
        response = await self.http.get_fixture(
            fixture_id,
            includes=["participants"],
        )
        if not response:
            return None
        if isinstance(response, list):
            response = response[0]
        return self._normalize_fixture(response)

    # ── head-to-head ────────────────────────────────────────────────── #
    async def get_head_to_head(
        self, team_a_id: str, team_b_id: str, league_id: str | None = None, **kwargs: Any
    ) -> NormalizedHeadToHead | None:
        response = await self.http.get_head_to_hhead(team_a_id, team_b_id)
        if not isinstance(response, list):
            response = []
        fixtures = [self._normalize_fixture(e) for e in response]
        team_a_wins = sum(
            1
            for f in fixtures
            if f.home_team_id == team_a_id
            and f.is_finished
            and (f.home_score or 0) > (f.away_score or 0)
        )
        team_b_wins = sum(
            1
            for f in fixtures
            if f.home_team_id == team_a_id
            and f.is_finished
            and (f.away_score or 0) > (f.home_score or 0)
        )
        draws = sum(
            1 for f in fixtures if f.is_finished and (f.home_score or 0) == (f.away_score or 0)
        )
        return NormalizedHeadToHead(
            provider=self.provider_name,
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
            params["team_id"] = team_id
        if fixture_id:
            params["fixture_id"] = fixture_id
        response = await self.http.get_injuries(params=params)
        if not isinstance(response, list):
            response = []
        return [self._normalize_injury(entry) for entry in response]

    async def get_suspensions(
        self, team_id: str | None = None, fixture_id: str | None = None, **kwargs: Any
    ) -> list[NormalizedSuspension]:
        params: dict[str, Any] = {}
        if team_id:
            params["team_id"] = team_id
        if fixture_id:
            params["fixture_id"] = fixture_id
        response = await self.http.get_sidelined(params=params)
        if not isinstance(response, list):
            response = []
        return [self._normalize_suspension(entry) for entry in response]

    # ── lineups ─────────────────────────────────────────────────────── #
    async def get_lineups(
        self, fixture_id: str, **kwargs: Any
    ) -> dict[str, NormalizedLineup] | list[NormalizedLineup]:
        response = await self.http.get_lineups(fixture_id)
        result: dict[str, NormalizedLineup] = {}
        if not isinstance(response, list):
            response = [response] if response else []
        for entry in response:
            lineup = self._normalize_lineup(entry)
            if lineup is not None:
                key = lineup.team_id or lineup.team_name or "unknown"
                result[key] = lineup
        return result

    async def get_predicted_lineups(
        self, fixture_id: str, **kwargs: Any
    ) -> NormalizedLineup | None:
        response = await self.http.get_predictions(fixture_id)
        if not response:
            return None
        if isinstance(response, list):
            response = response[0] if response else None
        if not isinstance(response, dict):
            return None
        # Sportmonks predictions include a predicted lineup field
        lineup_data = response.get("predicted_lineup") or response.get("lineup")
        if not lineup_data:
            return None
        return self._normalize_lineup(lineup_data, status=LineupStatus.PROJECTED)

    # ── match statistics ────────────────────────────────────────────── #
    async def get_match_statistics(
        self, fixture_id: str, **kwargs: Any
    ) -> NormalizedMatchStatistics | None:
        response = await self.http.get_match_statistics(fixture_id)
        if not response:
            return None
        if isinstance(response, list):
            response = response[0] if response else {}
        return self._normalize_match_statistics(response, fixture_id)

    # ── livescores ───────────────────────────────────────────────────── #
    async def get_inplay_livescores(self, **kwargs: Any) -> list[dict[str, Any]]:
        response = await self.http.get_inplay_livescores()
        if not isinstance(response, list):
            response = []
        return response

    async def get_all_livescores(self, **kwargs: Any) -> list[dict[str, Any]]:
        params = dict(kwargs)
        response = await self.http.get_all_livescores(params=params or {})
        if not isinstance(response, list):
            response = []
        return response

    async def get_latest_updated_livescores(self, **kwargs: Any) -> list[dict[str, Any]]:
        response = await self.http.get_last_updated_livescores()
        if not isinstance(response, list):
            response = []
        return response

    async def get_fixtures_live(self, **kwargs: Any) -> list[NormalizedFixture]:
        params: dict[str, Any] = {"live": "1"}
        if kwargs.get("league_id"):
            params["league_id"] = kwargs["league_id"]
        if kwargs.get("team_id"):
            params["team_id"] = kwargs["team_id"]
        response = await self.http.get_fixtures(params=params)
        if not isinstance(response, list):
            response = []
        return [self._normalize_fixture(entry) for entry in response]

    # ── news ──────────────────────────────────────────────────────────── #
    async def get_pre_match_news(self, **kwargs: Any) -> list[dict[str, Any]]:
        params = dict(kwargs)
        response = await self.http.get_pre_match_news(params=params or {})
        if not isinstance(response, list):
            response = []
        return response

    async def get_post_match_news(self, **kwargs: Any) -> list[dict[str, Any]]:
        params = dict(kwargs)
        response = await self.http.get_post_match_news(params=params or {})
        if not isinstance(response, list):
            response = []
        return response

    # ── bookmakers ────────────────────────────────────────────────────── #
    async def get_bookmakers(self, **kwargs: Any) -> list[dict[str, Any]]:
        params = dict(kwargs)
        if "fixture_id" in params:
            params["fixture_id"] = str(params["fixture_id"])
        response = await self.http.get_bookmakers(params=params or {})
        if not isinstance(response, list):
            response = []
        return response

    async def get_premium_bookmakers(self, **kwargs: Any) -> list[dict[str, Any]]:
        response = await self.http.get_premium_bookmakers()
        if not isinstance(response, list):
            response = []
        return response

    async def get_bookmaker(self, bookmaker_id: str, **kwargs: Any) -> dict[str, Any] | None:
        return await self.http.get_bookmaker(bookmaker_id)

    async def search_bookmakers(self, query: str, **kwargs: Any) -> list[dict[str, Any]]:
        response = await self.http.search_bookmakers(query)
        if not isinstance(response, list):
            response = []
        return response

    # ── states & types ────────────────────────────────────────────────── #
    async def get_states(self, **kwargs: Any) -> list[dict[str, Any]]:
        response = await self.http.get_states()
        if not isinstance(response, list):
            response = []
        return response

    async def get_state(self, state_id: str, **kwargs: Any) -> dict[str, Any] | None:
        return await self.http.get_state(state_id)

    async def get_types(self, **kwargs: Any) -> list[dict[str, Any]]:
        response = await self.http.get_types()
        if not isinstance(response, list):
            response = []
        return response

    async def get_type(self, type_id: str, **kwargs: Any) -> dict[str, Any] | None:
        return await self.http.get_type(type_id)

    async def get_type_by_entity(self, entity_id: str, **kwargs: Any) -> list[dict[str, Any]]:
        params = dict(kwargs)
        response = await self.http.get_type_by_entity(entity_id, params=params or {})
        if not isinstance(response, list):
            response = []
        return response

    # ── topscorers ────────────────────────────────────────────────────── #
    async def get_topscorers_by_season_id(
        self, season_id: str, **kwargs: Any
    ) -> list[dict[str, Any]]:
        response = await self.http.get_topscorers_by_season_id(season_id)
        if not isinstance(response, list):
            response = []
        return response

    async def get_topscorers_by_stage_id(
        self, stage_id: str, **kwargs: Any
    ) -> list[dict[str, Any]]:
        response = await self.http.get_topscorers_by_stage_id(stage_id)
        if not isinstance(response, list):
            response = []
        return response

    # ── match facts ───────────────────────────────────────────────────── #
    async def get_match_facts(self, **kwargs: Any) -> list[dict[str, Any]]:
        params = dict(kwargs)
        response = await self.http.get_match_facts(params=params or {})
        if not isinstance(response, list):
            response = []
        return response

    async def get_match_facts_by_fixture_id(
        self, fixture_id: str, **kwargs: Any
    ) -> list[dict[str, Any]]:
        response = await self.http.get_match_facts_by_fixture_id(fixture_id)
        if not isinstance(response, list):
            response = []
        return response

    async def get_match_facts_by_date_range(
        self, from_date: str, to_date: str, **kwargs: Any
    ) -> list[dict[str, Any]]:
        response = await self.http.get_match_facts_by_date_range(from_date, to_date)
        if not isinstance(response, list):
            response = []
        return response

    async def get_match_facts_by_league_id(
        self, league_id: str, **kwargs: Any
    ) -> list[dict[str, Any]]:
        params = dict(kwargs)
        response = await self.http.get_match_facts_by_league_id(league_id, params=params or {})
        if not isinstance(response, list):
            response = []
        return response

    # ── team rankings ────────────────────────────────────────────────── #
    async def get_team_rankings(self, **kwargs: Any) -> list[dict[str, Any]]:
        params = dict(kwargs)
        response = await self.http.get_team_rankings(params=params or {})
        if not isinstance(response, list):
            response = []
        return response

    async def get_team_rankings_by_team_id(
        self, team_id: str, **kwargs: Any
    ) -> list[dict[str, Any]]:
        response = await self.http.get_team_rankings_by_team_id(team_id)
        if not isinstance(response, list):
            response = []
        return response

    async def get_team_rankings_by_date(self, date: str, **kwargs: Any) -> list[dict[str, Any]]:
        params = dict(kwargs)
        response = await self.http.get_team_rankings_by_date(date, params=params or {})
        if not isinstance(response, list):
            response = []
        return response

    # ── expected (xG) ────────────────────────────────────────────────── #
    async def get_expected_by_team_id(self, team_id: str, **kwargs: Any) -> list[dict[str, Any]]:
        params = dict(kwargs)
        response = await self.http.get_expected_by_team_id(team_id, params=params or {})
        if not isinstance(response, list):
            response = []
        return response

    async def get_expected_by_player_id(
        self, player_id: str, **kwargs: Any
    ) -> list[dict[str, Any]]:
        params = dict(kwargs)
        response = await self.http.get_expected_by_player_id(player_id, params=params or {})
        if not isinstance(response, list):
            response = []
        return response

    # ── predictions ──────────────────────────────────────────────────── #
    async def get_probabilities(self, **kwargs: Any) -> list[dict[str, Any]]:
        params = dict(kwargs)
        response = await self.http.get_probabilities(params=params or {})
        if not isinstance(response, list):
            response = []
        return response

    async def get_probabilities_by_fixture_id(
        self, fixture_id: str, **kwargs: Any
    ) -> list[dict[str, Any]]:
        response = await self.http.get_probabilities_by_fixture_id(fixture_id)
        if not isinstance(response, list):
            response = []
        return response

    async def get_predictability_by_league_id(
        self, league_id: str, **kwargs: Any
    ) -> list[dict[str, Any]]:
        params = dict(kwargs)
        response = await self.http.get_predictability_by_league_id(league_id, params=params or {})
        if not isinstance(response, list):
            response = []
        return response

    async def get_value_bets(self, **kwargs: Any) -> list[dict[str, Any]]:
        params = dict(kwargs)
        response = await self.http.get_value_bets(params=params or {})
        if not isinstance(response, list):
            response = []
        return response

    async def get_value_bets_by_fixture_id(
        self, fixture_id: str, **kwargs: Any
    ) -> list[dict[str, Any]]:
        response = await self.http.get_value_bets_by_fixture_id(fixture_id)
        if not isinstance(response, list):
            response = []
        return response

    async def get_live_probabilities(self, **kwargs: Any) -> list[dict[str, Any]]:
        params = dict(kwargs)
        response = await self.http.get_live_probabilities(params=params or {})
        if not isinstance(response, list):
            response = []
        return response

    async def get_live_probabilities_by_fixture_id(
        self, fixture_id: str, **kwargs: Any
    ) -> list[dict[str, Any]]:
        response = await self.http.get_live_probabilities_by_fixture_id(fixture_id)
        if not isinstance(response, list):
            response = []
        return response

    # ── odds ─────────────────────────────────────────────────────────── #
    async def get_pre_match_odds(self, **kwargs: Any) -> list[dict[str, Any]]:
        params = dict(kwargs)
        fixture_id = params.pop("fixture_id", None)
        response: list[dict[str, Any]] = []
        if fixture_id:
            response = await self.http.get_odds(str(fixture_id))
        else:
            response = await self.http.get_odds_pre_match(params=params)
        if not isinstance(response, list):
            response = [response] if response else []
        return response

    async def get_in_play_odds(self, **kwargs: Any) -> list[dict[str, Any]]:
        params = dict(kwargs)
        fixture_id = params.pop("fixture_id", None)
        if fixture_id:
            return await self.http.get_live_odds_by_fixture_id(str(fixture_id))
        return await self.http.get_odds_live(params=params)

    # ── odds ────────────────────────────────────────────────────────── #
    async def get_odds(self, fixture_id: str | None = None, **kwargs: Any) -> NormalizedOdds | None:
        if not fixture_id:
            return None
        market_id = kwargs.get("market_id")
        response = await self.http.get_odds(
            fixture_id, params={"market_id": market_id} if market_id else None
        )
        if not isinstance(response, list):
            response = [response] if response else []
        markets: list[NormalizedOddsMarket] = []
        for entry in response:
            if not isinstance(entry, dict):
                continue
            markets.append(
                NormalizedOddsMarket(
                    market=entry.get("name", entry.get("market", "")),
                    selection=entry.get("label", entry.get("selection", "")),
                    odds=_to_float(entry.get("odds")),
                    is_main=True,
                    provider_metadata={"bookmaker": entry.get("bookmaker_name")},
                )
            )
        return NormalizedOdds(
            provider=self.provider_name,
            provider_fixture_id=fixture_id,
            markets=markets,
        )

    # ── players ─────────────────────────────────────────────────────── #
    async def get_players(
        self, team_id: str | None = None, **kwargs: Any
    ) -> list[NormalizedPlayer]:
        params: dict[str, Any] = {}
        if team_id:
            params["team_id"] = team_id
        response = await self.http.get_players(params=params)
        if not isinstance(response, list):
            response = []
        return [self._normalize_player(entry) for entry in response]

    async def get_standings(
        self,
        league_id: str | None = None,
        season_id: str | None = None,
        **kwargs: Any,
    ) -> NormalizedStandings | None:
        response = await self.http.get_standings(league_id=league_id, season_id=season_id)
        if not isinstance(response, list):
            response = []
        standings: list[NormalizedStanding] = []
        for entry in response:
            standings.append(self._normalize_standing(entry))
        return NormalizedStandings(
            provider=self.provider_name,
            league_id=league_id,
            season_id=season_id,
            standings=standings,
        )

    async def get_timezones(self, **kwargs: Any) -> list[str]:
        response = await self.http.get_timezones()
        if not isinstance(response, list):
            return []
        return [
            str(item.get("name") or item.get("timezone") or item)
            for item in response
            if isinstance(item, dict)
        ]

    async def get_countries(self, **kwargs: Any) -> list[dict[str, Any]]:
        response = await self.http.get_countries()
        if not isinstance(response, list):
            return []
        return [item for item in response if isinstance(item, dict)]

    async def get_venues(
        self, venue_id: str | None = None, team_id: str | None = None, **kwargs: Any
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if venue_id:
            params["id"] = venue_id
        if team_id:
            params["team_id"] = team_id
        response = await self.http.get_venues(params=params)
        if not isinstance(response, list):
            return []
        return [item for item in response if isinstance(item, dict)]

    async def get_coaches(
        self, team_id: str | None = None, coach_id: str | None = None, **kwargs: Any
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if team_id:
            params["team_id"] = team_id
        if coach_id:
            params["id"] = coach_id
        response = await self.http.get_coaches(params=params)
        if not isinstance(response, list):
            return []
        return [item for item in response if isinstance(item, dict)]

    async def get_transfers(
        self, player_id: str | None = None, team_id: str | None = None, **kwargs: Any
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if player_id:
            params["player_id"] = player_id
        if team_id:
            params["team_id"] = team_id
        response = await self.http.get_transfers(params=params)
        if not isinstance(response, list):
            return []
        return [item for item in response if isinstance(item, dict)]

    async def get_trophies(
        self, player_id: str | None = None, team_id: str | None = None, **kwargs: Any
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if player_id:
            params["player_id"] = player_id
        if team_id:
            params["team_id"] = team_id
        response = await self.http.get_trophies(params=params)
        if not isinstance(response, list):
            return []
        return [item for item in response if isinstance(item, dict)]

    async def get_predictions(self, fixture_id: str, **kwargs: Any) -> list[dict[str, Any]]:
        response = await self.http.get_predictions(fixture_id)
        if not response:
            return []
        if isinstance(response, list):
            return response
        return [response]

    async def get_sidelined(
        self, team_id: str | None = None, fixture_id: str | None = None, **kwargs: Any
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if team_id:
            params["team_id"] = team_id
        if fixture_id:
            params["fixture_id"] = fixture_id
        response = await self.http.get_sidelined(params=params)
        if not isinstance(response, list):
            return []
        return [item for item in response if isinstance(item, dict)]

    async def get_pre_match_odds(
        self, fixture_id: str | None = None, **kwargs: Any
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = kwargs.get("params") or {}
        if fixture_id:
            params["fixture_id"] = fixture_id
        response = await self.http.get_odds_pre_match(params=params)
        if not isinstance(response, list):
            return []
        return [item for item in response if isinstance(item, dict)]

    async def get_in_play_odds(
        self, fixture_id: str | None = None, **kwargs: Any
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = kwargs.get("params") or {}
        if fixture_id:
            params["fixture_id"] = fixture_id
        response = await self.http.get_odds_live(params=params)
        if not isinstance(response, list):
            return []
        return [item for item in response if isinstance(item, dict)]

    # ── health check ────────────────────────────────────────────────── #
    async def health_check(self) -> bool:
        try:
            await self.http.get_leagues(includes=[])
            return True
        except Exception as exc:
            logger.warning(f"Sportmonks health check failed: {exc}")
            return False

    # ── normalizers ─────────────────────────────────────────────────── #
    @staticmethod
    def _normalize_league(raw: dict[str, Any]) -> NormalizedLeague:
        country = raw.get("country", {})
        return NormalizedLeague(
            provider="sportmonks",
            provider_league_id=str(raw.get("id", "")),
            name=raw.get("name", ""),
            country=country.get("name") if isinstance(country, dict) else country,
            country_code=raw.get("iso2")
            or (country.get("code") if isinstance(country, dict) else None),
            season_count=raw.get("seasons"),
            provider_metadata={"slug": raw.get("slug"), "logo": raw.get("logo_path")},
        )

    @staticmethod
    def _normalize_season(raw: dict[str, Any], league_id: str | None) -> NormalizedSeason:
        return NormalizedSeason(
            provider="sportmonks",
            provider_season_id=str(raw.get("id", raw.get("season_id", ""))),
            league_id=league_id or "",
            name=raw.get("name", str(raw.get("id", ""))),
            year=raw.get("year"),
            start_date=raw.get("start"),
            end_date=raw.get("end"),
            is_current=raw.get("is_current", raw.get("current", False)) is True,
            provider_metadata={"league_id": raw.get("league_id"), "stage": raw.get("stage")},
        )

    @staticmethod
    def _normalize_team(
        raw: dict[str, Any], league_id: str | None = None, season_id: str | None = None
    ) -> NormalizedTeam:
        return NormalizedTeam(
            provider="sportmonks",
            provider_team_id=str(raw.get("id", "")),
            league_id=league_id,
            season_id=season_id,
            name=raw.get("name", ""),
            short_name=raw.get("short_code") or raw.get("short_name"),
            slug=raw.get("slug"),
            logo_url=raw.get("logo_path"),
            venue_name=raw.get("venue", {}).get("name")
            if isinstance(raw.get("venue"), dict)
            else None,
            venue_city=raw.get("venue", {}).get("city")
            if isinstance(raw.get("venue"), dict)
            else None,
            founded=raw.get("founded"),
            country=raw.get("country"),
            provider_metadata={"slug": raw.get("slug"), "abbreviation": raw.get("abbreviation")},
        )

    @staticmethod
    def _normalize_team_statistics(raw: dict[str, Any], team_id: str) -> NormalizedTeamStatistics:
        return NormalizedTeamStatistics(
            provider="sportmonks",
            provider_team_id=team_id,
            games_played=raw.get("fixtures"),
            wins=raw.get("wins"),
            draws=raw.get("draws"),
            losses=raw.get("losses"),
            goals_for=raw.get("scored"),
            goals_against=raw.get("conceded"),
            clean_sheets=raw.get("clean_sheets"),
            points=raw.get("points"),
            position=raw.get("position"),
            goals_per_game=_to_float(raw.get("scored_per_game")),
            goals_conceded_per_game=_to_float(raw.get("conceded_per_game")),
            provider_metadata={
                "form": raw.get("form"),
                "xg_for": raw.get("xg_for"),
                "xg_against": raw.get("xg_against"),
            },
        )

    @staticmethod
    def _normalize_fixture(raw: dict[str, Any]) -> NormalizedFixture:
        home = raw.get("home", {}) or {}
        away = raw.get("away", {}) or {}
        league = raw.get("league", {}) or {}
        participants = raw.get("participants") or []
        if isinstance(participants, dict):
            if isinstance(participants.get("data"), list):
                participants = participants["data"]
            elif "id" in participants:
                participants = [participants]
            else:
                participants = list(participants.values())
        unlocated_participants: list[dict[str, Any]] = []
        for participant in participants:
            if not isinstance(participant, dict):
                continue
            meta = participant.get("meta") or {}
            if isinstance(meta, list):
                meta = next((item for item in meta if isinstance(item, dict)), {})
            if not isinstance(meta, dict):
                meta = {}
            location = meta.get("location") or participant.get("location")
            if isinstance(location, dict):
                location = location.get("name") or location.get("code")
            location = str(location).lower() if location is not None else None
            normalized_participant = {
                "team_id": participant.get("id"),
                "name": participant.get("name"),
                "score": participant.get("score"),
            }
            if location == "home":
                home = normalized_participant
            elif location == "away":
                away = normalized_participant
            else:
                unlocated_participants.append(normalized_participant)

        for participant in unlocated_participants:
            if not home:
                home = participant
            elif not away:
                away = participant

        starting_at = raw.get("starting_at")
        if isinstance(starting_at, dict):
            kickoff_at = starting_at.get("date")
        else:
            kickoff_at = starting_at or raw.get("starts_at")

        raw_state = raw.get("state")
        if isinstance(raw_state, dict):
            raw_state = raw_state.get("state") or raw_state.get("name")

        return NormalizedFixture(
            provider="sportmonks",
            provider_fixture_id=str(raw.get("id", "")),
            league_id=str(league.get("id") or raw.get("league_id") or "") or None,
            provider_league_id=str(league.get("id") or raw.get("league_id") or "") or None,
            season_id=str(league.get("season_id") or raw.get("season_id") or "") or None,
            home_team_id=str(home.get("team_id", "")) if home else None,
            provider_home_team_id=str(home.get("team_id", "")) if home else None,
            away_team_id=str(away.get("team_id", "")) if away else None,
            provider_away_team_id=str(away.get("team_id", "")) if away else None,
            home_team_name=home.get("name"),
            away_team_name=away.get("name"),
            kickoff_at=kickoff_at,
            status=SportmonksProvider._normalize_status(raw_state),
            venue=raw.get("venue", {}).get("name") if isinstance(raw.get("venue"), dict) else None,
            referee=raw.get("referee", {}).get("name")
            if isinstance(raw.get("referee"), dict)
            else None,
            home_score=raw.get("home_score") if "home_score" in raw else home.get("score"),
            away_score=raw.get("away_score") if "away_score" in raw else away.get("score"),
            is_finished=SportmonksProvider._normalize_status(raw_state) == FixtureStatus.FINISHED,
            provider_metadata={
                "league_name": league.get("name") if league else None,
                "season_name": league.get("season_name") if league else None,
            },
        )

    @staticmethod
    def _normalize_injury(raw: dict[str, Any]) -> NormalizedInjury:
        player = raw.get("player", {}) or {}
        team = raw.get("team", {}) or {}
        injury = raw.get("injury", {}) or {}
        return NormalizedInjury(
            provider="sportmonks",
            provider_player_id=str(player.get("id", "")) if player else None,
            provider_team_id=str(team.get("id", "")) if team else None,
            team_id=str(team.get("id", "")) if team else None,
            player_name=player.get("name", ""),
            position=player.get("position"),
            injury_type=injury.get("type", injury.get("name")),
            severity=SportmonksProvider._normalize_severity(
                injury.get("severity") or raw.get("severity")
            ),
            description=injury.get("description", raw.get("description")),
            start_date=injury.get("start_date") or raw.get("start_date"),
            return_date=injury.get("return_date") or raw.get("return_date"),
            provider_metadata={
                "team_name": team.get("name"),
                "player_jersey": player.get("jersey_number"),
            },
        )

    @staticmethod
    def _normalize_suspension(raw: dict[str, Any]) -> NormalizedSuspension:
        player = raw.get("player", {}) or {}
        team = raw.get("team", {}) or {}
        return NormalizedSuspension(
            provider="sportmonks",
            provider_player_id=str(player.get("id", "")) if player else None,
            provider_team_id=str(team.get("id", "")) if team else None,
            team_id=str(team.get("id", "")) if team else None,
            player_name=player.get("name", ""),
            position=player.get("position"),
            reason=raw.get("reason", raw.get("type")),
            suspension_type=raw.get("suspension_type", raw.get("type")),
            suspended_from=raw.get("suspended_from"),
            suspended_until=raw.get("suspended_until"),
            provider_metadata={"team_name": team.get("name")},
        )

    @staticmethod
    def _normalize_lineup(
        raw: dict[str, Any], status: LineupStatus = LineupStatus.CONFIRMED
    ) -> NormalizedLineup | None:
        if not raw:
            return None
        team = raw.get("team", {}) or {}
        formation = raw.get("formation", {}).get("name")
        players_raw = raw.get("formation", {}).get("players", []) or []

        starting_xi: list[NormalizedLineupPlayer] = []
        substitutes: list[NormalizedLineupPlayer] = []
        for p in players_raw:
            player = NormalizedLineupPlayer(
                player_name=p.get("player", {}).get("name", "")
                if isinstance(p.get("player"), dict)
                else str(p.get("name", p)),
                position=p.get("position", p.get("pos")),
                jersey_number=p.get("jersey_number", p.get("number")),
                is_starter=True,
                is_substitute=False,
            )
            if p.get("substitute") or p.get("type") == "sub":
                player.is_substitute = True
                player.is_starter = False
                substitutes.append(player)
            else:
                starting_xi.append(player)

        return NormalizedLineup(
            provider="sportmonks",
            provider_fixture_id=str(raw.get("fixture_id", raw.get("id", ""))),
            team_id=str(team.get("id", "")) if team else None,
            team_name=team.get("name"),
            status=status,
            formation=formation,
            players=starting_xi + substitutes,
            starting_xi=starting_xi,
            substitutes=substitutes,
        )

    @staticmethod
    def _normalize_match_statistics(
        raw: dict[str, Any], fixture_id: str
    ) -> NormalizedMatchStatistics:
        return NormalizedMatchStatistics(
            provider="sportmonks",
            provider_fixture_id=fixture_id,
            possession={
                "home": _to_float(
                    raw.get("statistics", {}).get("possession_home")
                    if isinstance(raw.get("statistics"), dict)
                    else raw.get("possession_home")
                ),
                "away": _to_float(
                    raw.get("statistics", {}).get("possession_away")
                    if isinstance(raw.get("statistics"), dict)
                    else raw.get("possession_away")
                ),
            },
            shots={
                "home": _to_int(
                    raw.get("statistics", {}).get("shots_total_home")
                    if isinstance(raw.get("statistics"), dict)
                    else raw.get("shots_total_home")
                ),
                "away": _to_int(
                    raw.get("statistics", {}).get("shots_total_away")
                    if isinstance(raw.get("statistics"), dict)
                    else raw.get("shots_total_away")
                ),
            },
            xg={
                "home": _to_float(
                    raw.get("statistics", {}).get("expected_goals_home")
                    if isinstance(raw.get("statistics"), dict)
                    else raw.get("expected_goals_home")
                ),
                "away": _to_float(
                    raw.get("statistics", {}).get("expected_goals_away")
                    if isinstance(raw.get("statistics"), dict)
                    else raw.get("expected_goals_away")
                ),
            },
            is_finished=True,
            provider_metadata={"raw": raw},
        )

    @staticmethod
    def _normalize_player(raw: dict[str, Any]) -> NormalizedPlayer:
        team = raw.get("team", {}) or {}
        return NormalizedPlayer(
            provider="sportmonks",
            provider_player_id=str(raw.get("id", "")),
            team_id=str(team.get("id", "")) if team else None,
            first_name=raw.get("first_name"),
            last_name=raw.get("last_name"),
            full_name=raw.get("name", ""),
            position=raw.get("position", {}).get("name")
            if isinstance(raw.get("position"), dict)
            else raw.get("position"),
            date_of_birth=raw.get("date_of_birth"),
            nationality=raw.get("nationality", {}).get("name")
            if isinstance(raw.get("nationality"), dict)
            else raw.get("nationality"),
            height=raw.get("height"),
            weight=raw.get("weight"),
            footed=raw.get("foot"),
            provider_metadata={
                "team_name": team.get("name"),
                "jersey_number": raw.get("jersey_number"),
            },
        )

    @staticmethod
    def _normalize_standing(raw: dict[str, Any]) -> NormalizedStanding:
        return NormalizedStanding(
            team_id=str(raw.get("team_id", "")),
            team_name=raw.get("team", {}).get("name", "")
            if isinstance(raw.get("team"), dict)
            else raw.get("team_name", ""),
            position=raw.get("position", raw.get("rank", 0)),
            points=raw.get("points", 0),
            played=raw.get("fixtures", 0),
            wins=raw.get("wins", 0),
            draws=raw.get("draws", 0),
            losses=raw.get("losses", 0),
            goals_for=raw.get("scored", 0),
            goals_against=raw.get("conceded", 0),
            goal_difference=raw.get("scored", 0) - raw.get("conceded", 0),
            provider_metadata={"group": raw.get("group"), "status": raw.get("status")},
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

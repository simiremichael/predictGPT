"""Database-first prediction context service.

Builds the complete prediction context by:
1. Loading all data from the database first.
2. Checking data availability and freshness.
3. Fetching only missing/stale data from the provider.
4. Comparing provider data with database records.
5. Updating only changed records.
6. Returning a complete normalized prediction context.
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Any

from core.config import get_settings
from core.logging import get_logger
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from football_data.base import FootballDataProvider
from football_data.factory import get_football_provider
from football_data.models import (
    NormalizedForm,
    NormalizedHeadToHead,
    NormalizedInjury,
    NormalizedLineup,
    NormalizedLineupPlayer,
    NormalizedSuspension,
    NormalizedTeam,
    NormalizedTeamStatistics,
)
from models.league import ProviderLeague, ProviderTeam
from models.match import (
    ConfirmedLineup,
    HeadToHead,
    Injury,
    Match,
    MatchStatistics,
    PredictedLineup,
    Prediction,
    Suspension,
    TeamForm,
    TeamStatistics,
)
from prediction.base import PredictionInput
from services.data_availability import (
    FootballDataAvailabilityService,
    DataAvailabilityResult,
)

logger = get_logger(__name__)
settings = get_settings()

_HASH_FIELDS: dict[str, set[str]] = {
    "fixture": {
        "status",
        "kickoff_at",
        "home_team_id",
        "away_team_id",
        "home_team_name",
        "away_team_name",
        "home_score",
        "away_score",
        "is_finished",
    },
    "teams": {
        "id",
        "provider_team_id",
        "internal_id",
        "name",
        "short_name",
    },
    "statistics": {
        "provider_team_id",
        "internal_id",
        "league_id",
        "season_id",
        "is_home",
        "games_played",
        "wins",
        "draws",
        "losses",
        "goals_for",
        "goals_against",
        "clean_sheets",
        "points",
        "position",
        "form_rating",
        "average_possession",
        "average_shots",
        "average_xg",
        "average_xga",
        "goals_per_game",
        "goals_conceded_per_game",
    },
    "form": {
        "provider_team_id",
        "internal_id",
        "form_score",
        "form_description",
        "recent_matches",
        "recent_match_ids",
    },
    "h2h": {
        "team_a_id",
        "team_b_id",
        "team_a_internal_id",
        "team_b_internal_id",
        "team_a_wins",
        "team_b_wins",
        "draws",
        "avg_goals_per_game",
        "fixture_ids",
    },
    "injuries": {
        "provider_player_id",
        "provider_team_id",
        "team_id",
        "player_name",
        "position",
        "injury_type",
        "severity",
        "description",
        "start_date",
        "return_date",
        "is_startingXI_impact",
    },
    "suspensions": {
        "provider_player_id",
        "provider_team_id",
        "team_id",
        "player_name",
        "position",
        "reason",
        "suspension_type",
        "suspended_from",
        "suspended_until",
    },
    "lineups": {
        "provider_fixture_id",
        "team_id",
        "team_name",
        "formation",
        "players",
        "starting_xi",
        "players_json",
    },
}

_VOLATILE_HASH_FIELDS = {
    "id",
    "retrieved_at",
    "created_at",
    "updated_at",
    "valid_until",
    "provider_metadata",
}


class PredictionDataService:
    """Builds prediction context from database with provider fallback.

    This is the primary service that the prediction engine uses.
    It follows the database-first principle: always load from DB first,
    only call the provider for missing or stale data.
    """

    def __init__(self, provider: FootballDataProvider | None = None) -> None:
        self._provider = provider or get_football_provider()
        self._availability_service = FootballDataAvailabilityService()

    async def get_context(
        self,
        match_id: str,
        db_session: AsyncSession,
        required_data: list[str] | None = None,
    ) -> PredictionContext:
        """Build complete prediction context for a match.

        Args:
            match_id: Internal match UUID.
            db_session: SQLAlchemy async session.
            required_data: List of data types required. Defaults to standard set.

        Returns:
            PredictionContext with all required data.

        Raises:
            InsufficientDataError: If required data is unavailable and
            provider cannot be reached.
        """
        if required_data is None:
            required_data = [
                "fixture",
                "teams",
                "statistics",
                "form",
                "h2h",
                "injuries",
                "suspensions",
            ]

        logger.info(
            "Building prediction context",
            extra={"match_id": match_id, "required_data": required_data},
        )

        match = await self._load_match(db_session, match_id)
        if match is None:
            raise InsufficientDataError(f"Match {match_id} not found")

        db_data = await self._load_all_db_data(
            db_session, match, required_data
        )

        availability = self._availability_service.is_data_available(
            match_id, required_data, db_data
        )

        if not availability.fresh:
            db_data = await self._sync_missing_data(
                match_id, match, availability, db_data, db_session
            )
            availability = self._availability_service.is_data_available(
                match_id, required_data, db_data
            )

        context = await self._build_context(
            match, db_data, availability, required_data
        )

        context_hash = self._compute_context_hash(context)
        context.context_hash = context_hash

        logger.info(
            "Prediction context built",
            extra={
                "match_id": match_id,
                "context_hash": context_hash,
                "availability": availability.to_dict(),
            },
        )

        return context

    async def _load_match(
        self, db_session: AsyncSession, match_id: str
    ) -> Match | None:
        """Load match from database."""
        stmt = select(Match).where(Match.id == match_id)
        result = await db_session.execute(stmt)
        return result.scalar_one_or_none()

    async def _load_all_db_data(
        self,
        db_session: AsyncSession,
        match: Match,
        required_data: list[str],
    ) -> dict[str, Any]:
        """Load all required data from database."""
        db_data: dict[str, dict[str, Any] | None] = {}

        if "fixture" in required_data:
            db_data["fixture"] = self._serialize_match(match)

        if "teams" in required_data:
            db_data["teams"] = {
                "home": self._serialize_team(match, is_home=True),
                "away": self._serialize_team(match, is_home=False),
            }

        if "statistics" in required_data:
            home_stats = await self._load_latest_team_statistics(
                db_session, match.home_team_id, True
            )
            away_stats = await self._load_latest_team_statistics(
                db_session, match.away_team_id, False
            )
            db_data["statistics"] = {
                "home": self._serialize_team_statistics(home_stats) if home_stats else None,
                "away": self._serialize_team_statistics(away_stats) if away_stats else None,
            }

        if "form" in required_data:
            home_form = await self._load_latest_team_form(
                db_session, match.home_team_id
            )
            away_form = await self._load_latest_team_form(
                db_session, match.away_team_id
            )
            db_data["form"] = {
                "home": self._serialize_team_form(home_form) if home_form else None,
                "away": self._serialize_team_form(away_form) if away_form else None,
            }

        if "h2h" in required_data:
            h2h = await self._load_head_to_head(
                db_session, match.home_team_id, match.away_team_id
            )
            db_data["h2h"] = self._serialize_head_to_head(h2h) if h2h else None

        if "injuries" in required_data:
            injuries = await self._load_injuries(db_session, match.id)
            db_data["injuries"] = self._serialize_injuries(injuries)

        if "suspensions" in required_data:
            suspensions = await self._load_suspensions(db_session, match.id)
            db_data["suspensions"] = self._serialize_suspensions(suspensions)

        if "lineups" in required_data:
            predicted = await self._load_predicted_lineup(db_session, match.id)
            confirmed = await self._load_confirmed_lineup(db_session, match.id)
            db_data["lineups"] = {
                "predicted": self._serialize_lineup(predicted) if predicted else [],
                "confirmed": self._serialize_lineup(confirmed) if confirmed else [],
            }

        return db_data

    async def _load_latest_team_statistics(
        self, db_session: AsyncSession, team_id: str | None, _is_home: bool
    ) -> TeamStatistics | None:
        """Load most recent team statistics."""
        if team_id is None:
            return None
        stmt = (
            select(TeamStatistics)
            .where(TeamStatistics.internal_team_id == team_id)
            .order_by(TeamStatistics.retrieved_at.desc())
            .limit(1)
        )
        result = await db_session.execute(stmt)
        return result.scalar_one_or_none()

    async def _load_latest_team_form(
        self, db_session: AsyncSession, team_id: str | None
    ) -> TeamForm | None:
        """Load most recent team form."""
        if team_id is None:
            return None
        stmt = (
            select(TeamForm)
            .where(TeamForm.internal_team_id == team_id)
            .order_by(TeamForm.retrieved_at.desc())
            .limit(1)
        )
        result = await db_session.execute(stmt)
        return result.scalar_one_or_none()

    async def _load_head_to_head(
        self, db_session: AsyncSession, team_a_id: str, team_b_id: str
    ) -> HeadToHead | None:
        """Load head-to-head record."""
        stmt = (
            select(HeadToHead)
            .where(
                HeadToHead.team_a_internal_id == team_a_id,
                HeadToHead.team_b_internal_id == team_b_id,
            )
            .order_by(HeadToHead.retrieved_at.desc())
            .limit(1)
        )
        result = await db_session.execute(stmt)
        return result.scalar_one_or_none()

    async def _load_injuries(
        self, db_session: AsyncSession, match_id: str
    ) -> list[Injury]:
        match = await self._load_match(db_session, match_id)
        if match is None:
            return []
        team_ids = [
            team_id
            for team_id in (match.home_team_id, match.away_team_id)
            if team_id is not None
        ]
        stmt = select(Injury).where(
            Injury.provider_name == match.provider_name,
            Injury.internal_team_id.in_(team_ids),
        ).order_by(Injury.retrieved_at.desc())
        result = await db_session.execute(stmt)
        return result.scalars().all()

    async def _load_suspensions(
        self, db_session: AsyncSession, match_id: str
    ) -> list[Suspension]:
        match = await self._load_match(db_session, match_id)
        if match is None:
            return []
        team_ids = [
            team_id
            for team_id in (match.home_team_id, match.away_team_id)
            if team_id is not None
        ]
        stmt = select(Suspension).where(
            Suspension.provider_name == match.provider_name,
            Suspension.internal_team_id.in_(team_ids),
        ).order_by(Suspension.retrieved_at.desc())
        result = await db_session.execute(stmt)
        return result.scalars().all()

    async def _load_predicted_lineup(
        self, db_session: AsyncSession, match_id: str
    ) -> list[PredictedLineup]:
        stmt = (
            select(PredictedLineup)
            .where(PredictedLineup.internal_fixture_id == match_id)
            .order_by(PredictedLineup.retrieved_at.desc())
        )
        result = await db_session.execute(stmt)
        return result.scalars().all()

    async def _load_confirmed_lineup(
        self, db_session: AsyncSession, match_id: str
    ) -> list[ConfirmedLineup]:
        stmt = (
            select(ConfirmedLineup)
            .where(ConfirmedLineup.internal_fixture_id == match_id)
            .order_by(ConfirmedLineup.retrieved_at.desc())
        )
        result = await db_session.execute(stmt)
        return result.scalars().all()

    async def _sync_missing_data(
        self,
        match_id: str,
        match: Match,
        availability: DataAvailabilityResult,
        db_data: dict[str, dict[str, Any] | None],
        db_session: AsyncSession,
    ) -> dict[str, Any]:
        """Fetch missing or stale data and atomically persist changed records."""
        sync_needed = list(dict.fromkeys(availability.missing + availability.stale))
        if not sync_needed:
            return db_data

        logger.info(
            "Syncing missing data from provider",
            extra={
                "match_id": match_id,
                "sync_types": sync_needed,
            },
        )

        try:
            provider_data = await self._fetch_provider_data(
                match_id, match, sync_needed, db_session
            )
        except Exception as exc:
            logger.warning(
                "Provider sync failed, using database data",
                extra={
                    "match_id": match_id,
                    "error": str(exc),
                    "sync_types": sync_needed,
                },
            )
            return db_data

        try:
            async with db_session.begin_nested():
                await self._compare_and_update(
                    match_id,
                    provider_data,
                    sync_needed,
                    db_data,
                    db_session,
                )
            await db_session.commit()
            return await self._load_all_db_data(db_session, match, list(db_data))
        except Exception as exc:
            await db_session.rollback()
            logger.warning(
                "Provider data could not be persisted, using database data",
                extra={
                    "match_id": match_id,
                    "error": str(exc),
                    "sync_types": sync_needed,
                },
            )
            return db_data

    async def _resolve_provider_team_id(
        self,
        db_session: AsyncSession,
        internal_team_id: str | None,
        provider_name: str,
    ) -> str | None:
        if not internal_team_id:
            return None
        result = await db_session.execute(
            select(ProviderTeam.provider_team_id)
            .where(
                ProviderTeam.internal_team_id == internal_team_id,
                ProviderTeam.provider_name == provider_name,
                ProviderTeam.is_active.is_(True),
            )
            .limit(1)
        )
        return result.scalar_one_or_none() or internal_team_id

    async def _resolve_provider_league_id(
        self,
        db_session: AsyncSession,
        internal_league_id: str | None,
        provider_name: str,
    ) -> str | None:
        if not internal_league_id:
            return None
        result = await db_session.execute(
            select(ProviderLeague.provider_league_id)
            .where(
                ProviderLeague.internal_league_id == internal_league_id,
                ProviderLeague.provider_name == provider_name,
                ProviderLeague.is_active.is_(True),
            )
            .limit(1)
        )
        return result.scalar_one_or_none() or internal_league_id

    async def _resolve_provider_season_id(
        self,
        db_session: AsyncSession,
        internal_league_id: str | None,
        internal_season_id: str | None,
        provider_name: str,
    ) -> str | None:
        if not internal_league_id or not internal_season_id:
            return internal_season_id
        result = await db_session.execute(
            select(ProviderLeague.provider_season_id)
            .where(
                ProviderLeague.internal_league_id == internal_league_id,
                ProviderLeague.provider_name == provider_name,
                ProviderLeague.is_active.is_(True),
            )
            .limit(1)
        )
        return result.scalar_one_or_none() or internal_season_id

    async def _fetch_provider_data(
        self,
        match_id: str,
        match: Match,
        data_types: list[str],
        db_session: AsyncSession,
    ) -> dict[str, Any]:
        """Fetch only required data types from provider."""
        provider_data: dict[str, Any] = {}
        provider_name = match.provider_name
        home_provider_id = await self._resolve_provider_team_id(
            db_session, match.home_team_id, provider_name
        )
        away_provider_id = await self._resolve_provider_team_id(
            db_session, match.away_team_id, provider_name
        )
        provider_league_id = await self._resolve_provider_league_id(
            db_session, match.league_id, provider_name
        )
        provider_season_id = await self._resolve_provider_season_id(
            db_session, match.league_id, match.season_id, provider_name
        )

        if "fixture" in data_types:
            fixture = await self._provider.get_fixture(match.provider_fixture_id)
            if fixture is not None:
                provider_data["fixture"] = fixture

        if "statistics" in data_types:
            if home_provider_id:
                provider_data["home_statistics"] = await self._provider.get_team_statistics(
                    home_provider_id,
                    league_id=provider_league_id,
                    season_id=provider_season_id,
                )
            if away_provider_id:
                provider_data["away_statistics"] = await self._provider.get_team_statistics(
                    away_provider_id,
                    league_id=provider_league_id,
                    season_id=provider_season_id,
                )

        if "form" in data_types:
            if home_provider_id:
                provider_data["home_form"] = await self._provider.get_team_form(
                    home_provider_id,
                    fixture_id=match.provider_fixture_id,
                )
            if away_provider_id:
                provider_data["away_form"] = await self._provider.get_team_form(
                    away_provider_id,
                    fixture_id=match.provider_fixture_id,
                )

        if "h2h" in data_types:
            provider_data["h2h"] = await self._provider.get_head_to_head(
                home_provider_id or "",
                away_provider_id or "",
                league_id=provider_league_id,
            )

        if "injuries" in data_types:
            provider_data["injuries"] = []
            for team_id in (home_provider_id, away_provider_id):
                if team_id:
                    provider_data["injuries"].extend(
                        await self._provider.get_injuries(
                            team_id=team_id,
                            fixture_id=match.provider_fixture_id,
                        )
                    )

        if "suspensions" in data_types:
            provider_data["suspensions"] = []
            for team_id in (home_provider_id, away_provider_id):
                if team_id:
                    provider_data["suspensions"].extend(
                        await self._provider.get_suspensions(
                            team_id=team_id,
                            fixture_id=match.provider_fixture_id,
                        )
                    )

        if "lineups" in data_types:
            provider_data["predicted_lineup"] = await self._provider.get_predicted_lineups(
                match.provider_fixture_id
            )
            provider_data["confirmed_lineup"] = await self._provider.get_lineups(
                match.provider_fixture_id
            )

        return provider_data

    @staticmethod
    def _provider_item(provider_data: dict[str, Any], data_type: str) -> Any:
        provider_keys = {
            "fixture": "fixture",
            "statistics": ("home_statistics", "away_statistics"),
            "form": ("home_form", "away_form"),
            "h2h": "h2h",
            "injuries": "injuries",
            "suspensions": "suspensions",
            "lineups": ("predicted_lineup", "confirmed_lineup"),
        }
        keys = provider_keys.get(data_type, data_type)
        if isinstance(keys, str):
            return provider_data.get(keys)

        values = [provider_data.get(key) for key in keys]
        values = [value for value in values if value is not None]
        return values or None

    async def _compare_and_update(
        self,
        match_id: str,
        provider_data: dict[str, Any],
        data_types: list[str],
        db_data: dict[str, dict[str, Any] | None],
        db_session: AsyncSession,
    ) -> None:
        """Compare provider data with database and update only changes.

        Uses data hashes to detect meaningful changes.
        Runs in a transaction for atomicity.
        """
        for data_type in data_types:
            provider_item = self._provider_item(provider_data, data_type)
            if provider_item is None:
                continue

            existing_item = db_data.get(data_type)
            provider_hash = self._compute_data_hash(provider_item, data_type)
            existing_hash = self._compute_data_hash(existing_item, data_type)

            if provider_hash == existing_hash:
                logger.debug(
                    "Provider data unchanged, skipping update",
                    extra={
                        "match_id": match_id,
                        "data_type": data_type,
                        "hash": provider_hash,
                    },
                )
                continue

            logger.info(
                "Updating changed data",
                extra={
                    "match_id": match_id,
                    "data_type": data_type,
                    "old_hash": existing_hash,
                    "new_hash": provider_hash,
                },
            )

            await self._update_data_in_db(
                db_session, match_id, data_type, provider_item
            )

    async def _get_existing_hash(
        self,
        db_session: AsyncSession,
        match_id: str,
        data_type: str,
    ) -> str | None:
        """Get the stored data hash for a match data type."""
        stmt = select(Prediction).where(
            Prediction.match_id == match_id,
        ).order_by(Prediction.generated_at.desc()).limit(1)
        result = await db_session.execute(stmt)
        prediction = result.scalar_one_or_none()

        if prediction and prediction.feature_snapshot:
            snapshot = prediction.feature_snapshot
            if isinstance(snapshot, dict):
                return snapshot.get(f"{data_type}_hash")

        return None

    async def _update_data_in_db(
        self,
        db_session: AsyncSession,
        match_id: str,
        data_type: str,
        data: Any,
    ) -> None:
        """Update a specific data type in the database."""
        now = datetime.utcnow()

        if data_type == "injuries":
            await self._sync_injuries(db_session, match_id, data, now)
        elif data_type == "suspensions":
            await self._sync_suspensions(db_session, match_id, data, now)
        elif data_type == "fixture":
            await self._sync_fixture(db_session, match_id, data, now)
        elif data_type == "statistics":
            await self._sync_team_statistics(db_session, match_id, data, now)
        elif data_type == "form":
            await self._sync_team_form(db_session, match_id, data, now)
        elif data_type == "h2h":
            await self._sync_head_to_head(db_session, match_id, data, now)
        elif data_type == "lineups":
            await self._sync_lineups(db_session, match_id, data, now)

    @staticmethod
    def _payload(data: Any) -> dict[str, Any]:
        if hasattr(data, "model_dump"):
            return data.model_dump(mode="json")
        if isinstance(data, dict):
            return data
        return {}

    @staticmethod
    def _value(data: Any, key: str, default: Any = None) -> Any:
        if isinstance(data, dict):
            return data.get(key, default)
        return getattr(data, key, default)

    @staticmethod
    def _as_datetime(value: Any) -> datetime | None:
        if value is None or isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None

    async def _match_for_sync(
        self, db_session: AsyncSession, match_id: str
    ) -> Match | None:
        result = await db_session.execute(select(Match).where(Match.id == match_id))
        return result.scalar_one_or_none()

    async def _internal_team_id(
        self,
        db_session: AsyncSession,
        provider_name: str,
        provider_team_id: str | None,
        fallback: str | None,
    ) -> str | None:
        if provider_team_id:
            result = await db_session.execute(
                select(ProviderTeam.internal_team_id)
                .where(
                    ProviderTeam.provider_name == provider_name,
                    ProviderTeam.provider_team_id == provider_team_id,
                )
                .limit(1)
            )
            mapped = result.scalar_one_or_none()
            if mapped:
                return mapped
        return fallback or provider_team_id

    async def _sync_injuries(
        self,
        db_session: AsyncSession,
        match_id: str,
        injuries: list[Any],
        now: datetime,
    ) -> None:
        match = await self._match_for_sync(db_session, match_id)
        if match is None:
            return
        provider_name = self._provider.name
        team_ids = [
            team_id
            for team_id in (match.home_team_id, match.away_team_id)
            if team_id is not None
        ]
        if team_ids:
            await db_session.execute(
                delete(Injury).where(
                    Injury.provider_name == provider_name,
                    Injury.internal_team_id.in_(team_ids),
                )
            )
        for raw_injury in injuries:
            injury_data = self._payload(raw_injury)
            provider_team_id = injury_data.get("provider_team_id")
            internal_team_id = await self._internal_team_id(
                db_session, provider_name, provider_team_id, injury_data.get("team_id")
            )
            if internal_team_id not in team_ids:
                continue
            db_session.add(
                Injury(
                    provider_name=provider_name,
                    provider_player_id=injury_data.get("provider_player_id"),
                    provider_team_id=provider_team_id,
                    internal_team_id=internal_team_id,
                    player_name=injury_data.get("player_name"),
                    position=injury_data.get("position"),
                    injury_type=injury_data.get("injury_type"),
                    severity=injury_data.get("severity"),
                    description=injury_data.get("description"),
                    start_date=self._as_datetime(injury_data.get("start_date")),
                    return_date=self._as_datetime(injury_data.get("return_date")),
                    is_startingXI_impact=injury_data.get(
                        "is_startingXI_impact", False
                    ),
                    retrieved_at=now,
                    provider_metadata=injury_data.get("provider_metadata", {}),
                )
            )

    async def _sync_suspensions(
        self,
        db_session: AsyncSession,
        match_id: str,
        suspensions: list[Any],
        now: datetime,
    ) -> None:
        match = await self._match_for_sync(db_session, match_id)
        if match is None:
            return
        provider_name = self._provider.name
        team_ids = [
            team_id
            for team_id in (match.home_team_id, match.away_team_id)
            if team_id is not None
        ]
        if team_ids:
            await db_session.execute(
                delete(Suspension).where(
                    Suspension.provider_name == provider_name,
                    Suspension.internal_team_id.in_(team_ids),
                )
            )
        for raw_suspension in suspensions:
            suspension_data = self._payload(raw_suspension)
            provider_team_id = suspension_data.get("provider_team_id")
            internal_team_id = await self._internal_team_id(
                db_session,
                provider_name,
                provider_team_id,
                suspension_data.get("team_id"),
            )
            if internal_team_id not in team_ids:
                continue
            db_session.add(
                Suspension(
                    provider_name=provider_name,
                    provider_player_id=suspension_data.get("provider_player_id"),
                    provider_team_id=provider_team_id,
                    internal_team_id=internal_team_id,
                    player_name=suspension_data.get("player_name"),
                    position=suspension_data.get("position"),
                    reason=suspension_data.get("reason"),
                    suspension_type=suspension_data.get("suspension_type"),
                    suspended_from=self._as_datetime(
                        suspension_data.get("suspended_from")
                    ),
                    suspended_until=self._as_datetime(
                        suspension_data.get("suspended_until")
                    ),
                    retrieved_at=now,
                    provider_metadata=suspension_data.get("provider_metadata", {}),
                )
            )

    async def _sync_fixture(
        self,
        db_session: AsyncSession,
        match_id: str,
        fixture_data: Any,
        now: datetime,
    ) -> None:
        match = await self._match_for_sync(db_session, match_id)
        if match is None:
            return
        data = self._payload(fixture_data)
        status = data.get("status")
        if hasattr(status, "value"):
            status = status.value
        if status:
            match.status = str(status)
        if data.get("home_score") is not None:
            match.home_score = data["home_score"]
        if data.get("away_score") is not None:
            match.away_score = data["away_score"]
        if data.get("is_finished") is not None:
            match.is_finished = data["is_finished"]
        kickoff_at = self._as_datetime(data.get("kickoff_at") or data.get("date"))
        if kickoff_at:
            match.kickoff_at = kickoff_at
        match.retrieved_at = now

    async def _sync_team_statistics(
        self,
        db_session: AsyncSession,
        match_id: str,
        statistics: Any,
        now: datetime,
    ) -> None:
        match = await self._match_for_sync(db_session, match_id)
        if match is None:
            return
        items = statistics if isinstance(statistics, list) else [statistics]
        provider_name = self._provider.name
        for raw_stats in items:
            data = self._payload(raw_stats)
            provider_team_id = data.get("provider_team_id")
            if not provider_team_id:
                continue
            internal_team_id = await self._internal_team_id(
                db_session,
                provider_name,
                provider_team_id,
                data.get("internal_id"),
            )
            result = await db_session.execute(
                select(TeamStatistics)
                .where(
                    TeamStatistics.provider_name == provider_name,
                    TeamStatistics.provider_team_id == provider_team_id,
                    TeamStatistics.league_id == data.get("league_id"),
                    TeamStatistics.season_id == data.get("season_id"),
                )
                .limit(1)
            )
            existing = result.scalar_one_or_none()
            values = {
                "internal_team_id": internal_team_id,
                "is_home": data.get("is_home", False),
                "games_played": data.get("games_played"),
                "wins": data.get("wins"),
                "draws": data.get("draws"),
                "losses": data.get("losses"),
                "goals_for": data.get("goals_for"),
                "goals_against": data.get("goals_against"),
                "clean_sheets": data.get("clean_sheets"),
                "points": data.get("points"),
                "position": data.get("position"),
                "form_rating": data.get("form_rating"),
                "average_possession": data.get("average_possession"),
                "average_shots": data.get("average_shots"),
                "average_xg": data.get("average_xg"),
                "average_xga": data.get("average_xga"),
                "goals_per_game": data.get("goals_per_game"),
                "goals_conceded_per_game": data.get("goals_conceded_per_game"),
                "retrieved_at": now,
                "provider_metadata": data.get("provider_metadata", {}),
            }
            if existing is None:
                db_session.add(
                    TeamStatistics(
                        provider_name=provider_name,
                        provider_team_id=provider_team_id,
                        league_id=data.get("league_id") or match.league_id,
                        season_id=data.get("season_id") or match.season_id,
                        **values,
                    )
                )
            else:
                for key, value in values.items():
                    setattr(existing, key, value)

    async def _sync_team_form(
        self,
        db_session: AsyncSession,
        match_id: str,
        forms: Any,
        now: datetime,
    ) -> None:
        match = await self._match_for_sync(db_session, match_id)
        if match is None:
            return
        items = forms if isinstance(forms, list) else [forms]
        provider_name = self._provider.name
        for raw_form in items:
            data = self._payload(raw_form)
            provider_team_id = data.get("provider_team_id")
            if not provider_team_id:
                continue
            internal_team_id = await self._internal_team_id(
                db_session,
                provider_name,
                provider_team_id,
                data.get("internal_id"),
            )
            result = await db_session.execute(
                select(TeamForm)
                .where(
                    TeamForm.provider_name == provider_name,
                    TeamForm.provider_team_id == provider_team_id,
                )
                .limit(1)
            )
            existing = result.scalar_one_or_none()
            values = {
                "internal_team_id": internal_team_id,
                "fixture_id": match_id,
                "form_score": data.get("form_score"),
                "form_description": data.get("form_description"),
                "recent_match_ids": [
                    item.get("provider_fixture_id") or item.get("id")
                    for item in data.get("recent_matches", [])
                    if isinstance(item, dict)
                ],
                "retrieved_at": now,
                "provider_metadata": data.get("provider_metadata", {}),
            }
            if existing is None:
                db_session.add(
                    TeamForm(
                        provider_name=provider_name,
                        provider_team_id=provider_team_id,
                        **values,
                    )
                )
            else:
                for key, value in values.items():
                    setattr(existing, key, value)

    async def _sync_head_to_head(
        self,
        db_session: AsyncSession,
        match_id: str,
        h2h_data: Any,
        now: datetime,
    ) -> None:
        match = await self._match_for_sync(db_session, match_id)
        if match is None or h2h_data is None:
            return
        data = self._payload(h2h_data)
        provider_name = self._provider.name
        team_a_id = data.get("team_a_id") or match.home_team_id
        team_b_id = data.get("team_b_id") or match.away_team_id
        result = await db_session.execute(
            select(HeadToHead)
            .where(
                HeadToHead.provider_name == provider_name,
                HeadToHead.team_a_id == team_a_id,
                HeadToHead.team_b_id == team_b_id,
            )
            .limit(1)
        )
        existing = result.scalar_one_or_none()
        values = {
            "league_id": data.get("league_id") or match.league_id,
            "team_a_internal_id": match.home_team_id,
            "team_b_internal_id": match.away_team_id,
            "team_a_wins": data.get("team_a_wins"),
            "team_b_wins": data.get("team_b_wins"),
            "draws": data.get("draws"),
            "avg_goals_per_game": data.get("avg_goals_per_game"),
            "fixture_ids": data.get("fixture_ids"),
            "retrieved_at": now,
        }
        if existing is None:
            db_session.add(
                HeadToHead(
                    provider_name=provider_name,
                    team_a_id=team_a_id,
                    team_b_id=team_b_id,
                    **values,
                )
            )
        else:
            for key, value in values.items():
                setattr(existing, key, value)

    async def _sync_lineups(
        self,
        db_session: AsyncSession,
        match_id: str,
        lineups: Any,
        now: datetime,
    ) -> None:
        match = await self._match_for_sync(db_session, match_id)
        if match is None:
            return
        provider_name = self._provider.name
        predicted = lineups.get("predicted_lineup") if isinstance(lineups, dict) else None
        confirmed = lineups.get("confirmed_lineup") if isinstance(lineups, dict) else None
        for model, raw_lineup, is_confirmed in (
            (ConfirmedLineup, confirmed, True),
            (PredictedLineup, predicted, False),
        ):
            if raw_lineup is None:
                continue
            items = raw_lineup if isinstance(raw_lineup, list) else [raw_lineup]
            if (
                isinstance(raw_lineup, dict)
                and "provider_fixture_id" not in raw_lineup
                and "team_id" not in raw_lineup
            ):
                items = list(raw_lineup.values())
            await db_session.execute(
                delete(model).where(
                    model.provider_name == provider_name,
                    model.internal_fixture_id == match_id,
                )
            )
            for raw_item in items:
                data = self._payload(raw_item)
                provider_team_id = data.get("team_id")
                internal_team_id = await self._internal_team_id(
                    db_session,
                    provider_name,
                    provider_team_id,
                    data.get("internal_id"),
                )
                players = data.get("players") or data.get("starting_xi") or data.get("players_json") or []
                db_session.add(
                    model(
                        provider_name=provider_name,
                        provider_fixture_id=data.get("provider_fixture_id")
                        or match.provider_fixture_id,
                        internal_fixture_id=match_id,
                        team_id=internal_team_id,
                        team_name=data.get("team_name"),
                        formation=data.get("formation"),
                        players_json=players,
                        retrieved_at=now,
                    )
                )


    def _serialize_match(self, match: Match | None) -> dict[str, Any] | None:
        if match is None:
            return None
        return {
            "id": match.id,
            "status": match.status,
            "kickoff_at": match.kickoff_at.isoformat() if match.kickoff_at else None,
            "home_team_id": match.home_team_id,
            "away_team_id": match.away_team_id,
            "home_team_name": match.home_team_name,
            "away_team_name": match.away_team_name,
            "is_finished": match.is_finished,
            "home_score": match.home_score,
            "away_score": match.away_score,
            "retrieved_at": match.retrieved_at.isoformat() if match.retrieved_at else None,
            "provider_name": match.provider_name,
            "provider_fixture_id": match.provider_fixture_id,
        }

    def _serialize_team(self, match: Match, is_home: bool) -> dict[str, Any] | None:
        team_id = match.home_team_id if is_home else match.away_team_id
        team_name = match.home_team_name if is_home else match.away_team_name
        if not team_id:
            return None
        return {
            "id": team_id,
            "provider": match.provider_name,
            "provider_team_id": team_id,
            "internal_id": team_id,
            "name": team_name,
            "retrieved_at": match.retrieved_at.isoformat() if match.retrieved_at else None,
        }

    def _serialize_team_statistics(
        self, stats: TeamStatistics | None
    ) -> dict[str, Any] | None:
        if stats is None:
            return None
        return {
            "id": stats.id,
            "provider": stats.provider_name,
            "provider_team_id": stats.provider_team_id,
            "internal_id": stats.internal_team_id,
            "league_id": stats.league_id,
            "season_id": stats.season_id,
            "is_home": stats.is_home,
            "games_played": stats.games_played,
            "wins": stats.wins,
            "draws": stats.draws,
            "losses": stats.losses,
            "goals_for": stats.goals_for,
            "goals_against": stats.goals_against,
            "clean_sheets": stats.clean_sheets,
            "points": stats.points,
            "position": stats.position,
            "form_rating": stats.form_rating,
            "average_possession": stats.average_possession,
            "average_shots": stats.average_shots,
            "average_xg": stats.average_xg,
            "average_xga": stats.average_xga,
            "goals_per_game": stats.goals_per_game,
            "goals_conceded_per_game": stats.goals_conceded_per_game,
            "retrieved_at": stats.retrieved_at.isoformat() if stats.retrieved_at else None,
        }

    def _serialize_team_form(self, form: TeamForm | None) -> dict[str, Any] | None:
        if form is None:
            return None
        return {
            "id": form.id,
            "provider": form.provider_name,
            "provider_team_id": form.provider_team_id,
            "internal_id": form.internal_team_id,
            "form_score": form.form_score,
            "form_description": form.form_description,
            "recent_match_ids": form.recent_match_ids,
            "retrieved_at": form.retrieved_at.isoformat() if form.retrieved_at else None,
        }

    def _serialize_head_to_head(
        self, h2h: HeadToHead | None
    ) -> dict[str, Any] | None:
        if h2h is None:
            return None
        return {
            "id": h2h.id,
            "provider": h2h.provider_name,
            "team_a_id": h2h.team_a_internal_id or h2h.team_a_id,
            "team_b_id": h2h.team_b_internal_id or h2h.team_b_id,
            "league_id": h2h.league_id,
            "team_a_wins": h2h.team_a_wins,
            "team_b_wins": h2h.team_b_wins,
            "draws": h2h.draws,
            "avg_goals_per_game": h2h.avg_goals_per_game,
            "fixture_ids": h2h.fixture_ids,
            "retrieved_at": h2h.retrieved_at.isoformat() if h2h.retrieved_at else None,
        }

    def _serialize_injuries(
        self, injuries: list[Injury]
    ) -> list[dict[str, Any]]:
        return [
            {
                "id": i.id,
                "provider": i.provider_name,
                "provider_player_id": i.provider_player_id,
                "provider_team_id": i.provider_team_id,
                "team_id": i.internal_team_id,
                "player_name": i.player_name,
                "position": i.position,
                "injury_type": i.injury_type,
                "severity": i.severity,
                "description": i.description,
                "start_date": i.start_date.isoformat() if i.start_date else None,
                "return_date": i.return_date.isoformat() if i.return_date else None,
                "is_startingXI_impact": i.is_startingXI_impact,
                "retrieved_at": i.retrieved_at.isoformat() if i.retrieved_at else None,
            }
            for i in injuries
        ]

    def _serialize_suspensions(
        self, suspensions: list[Suspension]
    ) -> list[dict[str, Any]]:
        return [
            {
                "id": s.id,
                "provider": s.provider_name,
                "provider_player_id": s.provider_player_id,
                "provider_team_id": s.provider_team_id,
                "team_id": s.internal_team_id,
                "player_name": s.player_name,
                "position": s.position,
                "reason": s.reason,
                "suspension_type": s.suspension_type,
                "suspended_from": s.suspended_from.isoformat() if s.suspended_from else None,
                "suspended_until": s.suspended_until.isoformat()
                if s.suspended_until
                else None,
                "retrieved_at": s.retrieved_at.isoformat() if s.retrieved_at else None,
            }
            for s in suspensions
        ]

    def _serialize_lineup(
        self,
        lineup: PredictedLineup | ConfirmedLineup | list[PredictedLineup | ConfirmedLineup] | None,
    ) -> list[dict[str, Any]]:
        if lineup is None:
            return []
        items = lineup if isinstance(lineup, list) else [lineup]
        return [
            {
                "id": item.id,
                "provider": item.provider_name,
                "provider_fixture_id": item.provider_fixture_id,
                "team_id": item.team_id,
                "team_name": item.team_name,
                "formation": item.formation,
                "players_json": item.players_json,
                "retrieved_at": item.retrieved_at.isoformat() if item.retrieved_at else None,
            }
            for item in items
        ]

    def _stable_hash_value(self, value: Any, data_type: str | None = None) -> Any:
        if isinstance(value, dict):
            allowed = _HASH_FIELDS.get(data_type or "")
            if allowed:
                value = {key: item for key, item in value.items() if key in allowed}
            return {
                key: self._stable_hash_value(item, data_type)
                for key, item in sorted(value.items())
                if key not in _VOLATILE_HASH_FIELDS
            }
        if isinstance(value, (list, tuple)):
            child_type = data_type if data_type in {"injuries", "suspensions", "lineups"} else None
            return [self._stable_hash_value(item, child_type) for item in value]
        if hasattr(value, "value"):
            return value.value
        if isinstance(value, datetime):
            return value.isoformat()
        return value

    def _compute_data_hash(self, data: Any, data_type: str | None = None) -> str:
        """Compute a stable SHA-256 hash of meaningful data only."""
        canonical = json.dumps(
            self._stable_hash_value(data, data_type),
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _compute_context_hash(self, context: "PredictionContext") -> str:
        """Compute hash of the complete prediction context."""
        hashable = {
            "fixture": context.fixture,
            "home_team": context.home_team,
            "away_team": context.away_team,
            "home_form": context.home_form,
            "away_form": context.away_form,
            "home_statistics": context.home_statistics,
            "away_statistics": context.away_statistics,
            "h2h": context.h2h,
            "injuries": context.injuries,
            "suspensions": context.suspensions,
            "predicted_lineup": context.predicted_lineup,
            "confirmed_lineup": context.confirmed_lineup,
            "model_version": context.model_version,
        }
        canonical = json.dumps(
            self._stable_hash_value(hashable),
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    async def _build_context(
        self,
        match: Match,
        db_data: dict[str, dict[str, Any] | None],
        availability: DataAvailabilityResult,
        required_data: list[str],
    ) -> "PredictionContext":
        """Build the PredictionContext from loaded data."""
        home_team = db_data.get("teams", {}).get("home")
        away_team = db_data.get("teams", {}).get("away")
        home_stats = db_data.get("statistics", {}).get("home")
        away_stats = db_data.get("statistics", {}).get("away")
        home_form = db_data.get("form", {}).get("home")
        away_form = db_data.get("form", {}).get("away")
        h2h = db_data.get("h2h")
        injuries = db_data.get("injuries", []) or []
        suspensions = db_data.get("suspensions", []) or []
        lineups = db_data.get("lineups", {}) or {}

        return PredictionContext(
            match_id=match.id,
            fixture=db_data.get("fixture"),
            home_team=home_team,
            away_team=away_team,
            home_statistics=home_stats,
            away_statistics=away_stats,
            home_form=home_form,
            away_form=away_form,
            h2h=h2h,
            injuries=injuries,
            suspensions=suspensions,
            predicted_lineup=lineups.get("predicted"),
            confirmed_lineup=lineups.get("confirmed"),
            availability=availability,
            match=match,
        )


class PredictionContext:
    """Complete prediction context for the prediction engine."""

    def __init__(
        self,
        match_id: str,
        fixture: dict[str, Any] | None = None,
        home_team: dict[str, Any] | None = None,
        away_team: dict[str, Any] | None = None,
        home_statistics: dict[str, Any] | None = None,
        away_statistics: dict[str, Any] | None = None,
        home_form: dict[str, Any] | None = None,
        away_form: dict[str, Any] | None = None,
        h2h: dict[str, Any] | None = None,
        injuries: list[dict[str, Any]] | None = None,
        suspensions: list[dict[str, Any]] | None = None,
        predicted_lineup: dict[str, Any] | list[dict[str, Any]] | None = None,
        confirmed_lineup: dict[str, Any] | list[dict[str, Any]] | None = None,
        availability: DataAvailabilityResult | None = None,
        match: Match | None = None,
        context_hash: str = "",
        model_version: str = "poisson-v1.0.0",
    ) -> None:
        self.match_id = match_id
        self.fixture = fixture
        self.home_team = home_team
        self.away_team = away_team
        self.home_statistics = home_statistics
        self.away_statistics = away_statistics
        self.home_form = home_form
        self.away_form = away_form
        self.h2h = h2h
        self.injuries = injuries or []
        self.suspensions = suspensions or []
        self.predicted_lineup = predicted_lineup
        self.confirmed_lineup = confirmed_lineup
        self.availability = availability
        self.match = match
        self.context_hash = context_hash
        self.model_version = model_version

    def to_prediction_input(self) -> PredictionInput:
        """Convert context to PredictionInput for the model."""
        provider = self.match.provider_name if self.match else "api_football"
        home_team_data = self.home_team or {}
        away_team_data = self.away_team or {}
        home_stats_data = self.home_statistics or {}
        away_stats_data = self.away_statistics or {}
        home_form_data = self.home_form or {}
        away_form_data = self.away_form or {}

        def normalized_team(data: dict[str, Any]) -> NormalizedTeam | None:
            team_id = data.get("id")
            if not team_id:
                return None
            return NormalizedTeam(
                provider=data.get("provider", provider),
                provider_team_id=data.get("provider_team_id") or team_id,
                internal_id=data.get("internal_id") or team_id,
                name=data.get("name", ""),
                short_name=data.get("short_name"),
                logo_url=data.get("logo_url"),
                venue_city=data.get("venue_city"),
                country=data.get("country"),
            )

        def normalized_statistics(
            data: dict[str, Any],
        ) -> NormalizedTeamStatistics | None:
            if not data:
                return None
            return NormalizedTeamStatistics(
                provider=data.get("provider", provider),
                provider_team_id=data.get("provider_team_id") or data.get("id"),
                internal_id=data.get("internal_id"),
                league_id=data.get("league_id"),
                season_id=data.get("season_id"),
                is_home=data.get("is_home", False),
                games_played=data.get("games_played"),
                wins=data.get("wins"),
                draws=data.get("draws"),
                losses=data.get("losses"),
                goals_for=data.get("goals_for"),
                goals_against=data.get("goals_against"),
                clean_sheets=data.get("clean_sheets"),
                points=data.get("points"),
                position=data.get("position"),
                form_rating=data.get("form_rating"),
                average_possession=data.get("average_possession"),
                average_shots=data.get("average_shots"),
                average_xg=data.get("average_xg"),
                average_xga=data.get("average_xga"),
                goals_per_game=data.get("goals_per_game"),
                goals_conceded_per_game=data.get("goals_conceded_per_game"),
            )

        def normalized_form(data: dict[str, Any]) -> NormalizedForm | None:
            if not data:
                return None
            return NormalizedForm(
                provider=data.get("provider", provider),
                provider_team_id=data.get("provider_team_id") or data.get("id"),
                internal_id=data.get("internal_id"),
                form_score=data.get("form_score"),
                form_description=data.get("form_description"),
            )

        def normalized_injury(data: dict[str, Any]) -> NormalizedInjury:
            return NormalizedInjury(
                provider=data.get("provider", provider),
                provider_player_id=data.get("provider_player_id"),
                provider_team_id=data.get("provider_team_id"),
                team_id=data.get("team_id"),
                player_name=data.get("player_name"),
                position=data.get("position"),
                injury_type=data.get("injury_type"),
                severity=data.get("severity"),
                description=data.get("description"),
                start_date=data.get("start_date"),
                return_date=data.get("return_date"),
                is_startingXI_impact=data.get("is_startingXI_impact", False),
            )

        def normalized_suspension(data: dict[str, Any]) -> NormalizedSuspension:
            return NormalizedSuspension(
                provider=data.get("provider", provider),
                provider_player_id=data.get("provider_player_id"),
                provider_team_id=data.get("provider_team_id"),
                team_id=data.get("team_id"),
                player_name=data.get("player_name"),
                position=data.get("position"),
                reason=data.get("reason"),
                suspension_type=data.get("suspension_type"),
                suspended_from=data.get("suspended_from"),
                suspended_until=data.get("suspended_until"),
            )

        def normalized_lineup(
            data: dict[str, Any] | list[dict[str, Any]] | None,
        ) -> NormalizedLineup | None:
            if isinstance(data, list):
                data = data[0] if data else None
            if not data:
                return None
            players = data.get("players_json") or []
            return NormalizedLineup(
                provider=data.get("provider", provider),
                provider_fixture_id=data.get("provider_fixture_id", ""),
                team_id=data.get("team_id"),
                team_name=data.get("team_name"),
                formation=data.get("formation"),
                players=[
                    NormalizedLineupPlayer(
                        player_name=player.get("player_name", ""),
                        position=player.get("position"),
                        jersey_number=player.get("jersey_number"),
                        is_starter=player.get("is_starter", True),
                        is_substitute=player.get("is_substitute", False),
                    )
                    for player in players
                    if isinstance(player, dict)
                ],
            )

        h2h_data = self.h2h or {}
        return PredictionInput(
            match_id=self.match_id,
            home_team_id=home_team_data.get("id", "") or "",
            away_team_id=away_team_data.get("id", "") or "",
            home_team_name=home_team_data.get("name", "") or "",
            away_team_name=away_team_data.get("name", "") or "",
            league_id=self.match.league_id if self.match else "",
            season_id=self.match.season_id if self.match else None,
            kickoff_at=self.match.kickoff_at if self.match else None,
            home_team=normalized_team(home_team_data),
            away_team=normalized_team(away_team_data),
            home_team_stats=normalized_statistics(home_stats_data),
            away_team_stats=normalized_statistics(away_stats_data),
            home_form=normalized_form(home_form_data),
            away_form=normalized_form(away_form_data),
            h2h=NormalizedHeadToHead(
                provider=h2h_data.get("provider", provider),
                team_a_id=h2h_data.get("team_a_id"),
                team_b_id=h2h_data.get("team_b_id"),
                league_id=h2h_data.get("league_id"),
                team_a_wins=h2h_data.get("team_a_wins"),
                team_b_wins=h2h_data.get("team_b_wins"),
                draws=h2h_data.get("draws"),
                avg_goals_per_game=h2h_data.get("avg_goals_per_game"),
            )
            if h2h_data
            else None,
            injuries=[normalized_injury(item) for item in self.injuries],
            suspensions=[normalized_suspension(item) for item in self.suspensions],
            predicted_lineup=normalized_lineup(self.predicted_lineup),
            confirmed_lineup=normalized_lineup(self.confirmed_lineup),
            provider=provider,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "match_id": self.match_id,
            "fixture": self.fixture,
            "home_team": self.home_team,
            "away_team": self.away_team,
            "home_statistics": self.home_statistics,
            "away_statistics": self.away_statistics,
            "home_form": self.home_form,
            "away_form": self.away_form,
            "h2h": self.h2h,
            "injuries": self.injuries,
            "suspensions": self.suspensions,
            "predicted_lineup": self.predicted_lineup,
            "confirmed_lineup": self.confirmed_lineup,
            "context_hash": self.context_hash,
            "model_version": self.model_version,
            "availability": self.availability.to_dict() if self.availability else None,
        }


class InsufficientDataError(Exception):
    """Raised when required data is unavailable and cannot be fetched."""
    pass

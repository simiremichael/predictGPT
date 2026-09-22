"""Data availability service.

Determines whether required football data is available, fresh, or stale.
Used by the prediction pipeline to decide whether provider sync is needed.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from core.config import get_settings
from core.logging import get_logger

logger = get_logger(__name__)


class DataAvailabilityResult:
    """Result of checking data availability for a match."""

    def __init__(
        self,
        available: bool,
        fresh: bool,
        missing: list[str],
        stale: list[str],
        last_updated: str | None,
    ) -> None:
        self.available = available
        self.fresh = fresh
        self.missing = missing
        self.stale = stale
        self.last_updated = last_updated

    def to_dict(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "fresh": self.fresh,
            "missing": self.missing,
            "stale": self.stale,
            "last_updated": self.last_updated,
        }

    def __repr__(self) -> str:
        return (
            f"DataAvailabilityResult(available={self.available}, "
            f"fresh={self.fresh}, missing={self.missing}, "
            f"stale={self.stale})"
        )


class FootballDataAvailabilityService:
    """Determines whether required football data is available and fresh."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._stale_thresholds: dict[str, timedelta] = {
            "fixture": timedelta(hours=24),
            "teams": timedelta(hours=48),
            "statistics": timedelta(hours=72),
            "form": timedelta(hours=24),
            "h2h": timedelta(days=7),
            "injuries": timedelta(hours=6),
            "suspensions": timedelta(hours=6),
            "lineups": timedelta(hours=1),
            "confirmed_lineups": timedelta(minutes=30),
            "odds": timedelta(hours=4),
            "research": timedelta(hours=12),
        }

    @staticmethod
    def _latest_retrieved_at(value: Any) -> datetime | None:
        """Return the newest retrieval timestamp nested in a record."""
        if isinstance(value, dict):
            candidates = [value.get("retrieved_at")]
            candidates.extend(
                FootballDataAvailabilityService._latest_retrieved_at(item)
                for item in value.values()
                if item is not value
            )
        elif isinstance(value, (list, tuple)):
            candidates = [
                FootballDataAvailabilityService._latest_retrieved_at(item)
                for item in value
            ]
        else:
            candidates = [value] if isinstance(value, (datetime, str)) else []

        parsed: list[datetime] = []
        for candidate in candidates:
            if candidate is None:
                continue
            if isinstance(candidate, str):
                try:
                    candidate = datetime.fromisoformat(candidate)
                except ValueError:
                    continue
            if candidate.tzinfo is None:
                candidate = candidate.replace(tzinfo=timezone.utc)
            else:
                candidate = candidate.astimezone(timezone.utc)
            parsed.append(candidate)

        return max(parsed, default=None)

    def is_data_available(
        self,
        match_id: str,
        required_data: list[str],
        db_data: dict[str, Any],
    ) -> DataAvailabilityResult:
        """Check whether required data is available and fresh.

        Args:
            match_id: Match identifier for logging.
            required_data: List of data types to check.
            db_data: Dict mapping data type to its DB record metadata
                (with keys like 'retrieved_at', 'updated_at', 'status').

        Returns:
            DataAvailabilityResult with availability and freshness info.
        """
        missing: list[str] = []
        stale: list[str] = []
        last_updated: str | None = None
        all_fresh = True

        now = datetime.now(timezone.utc)

        for data_type in required_data:
            record = db_data.get(data_type)

            if record is None:
                missing.append(data_type)
                all_fresh = False
                logger.debug(
                    "Data missing",
                    extra={
                        "match_id": match_id,
                        "data_type": data_type,
                        "reason": "not_in_database",
                    },
                )
                continue

            retrieved_at = self._latest_retrieved_at(record)
            if retrieved_at is None:
                missing.append(data_type)
                all_fresh = False
                continue

            if last_updated is None or retrieved_at > datetime.fromisoformat(last_updated):
                last_updated = retrieved_at.isoformat()

            threshold = self._stale_thresholds.get(data_type, timedelta(hours=24))
            age = now - retrieved_at
            if age > threshold:
                stale.append(data_type)
                all_fresh = False
                logger.debug(
                    "Data stale",
                    extra={
                        "match_id": match_id,
                        "data_type": data_type,
                        "age_seconds": age.total_seconds(),
                        "threshold_seconds": threshold.total_seconds(),
                    },
                )

        available = len(missing) == 0

        result = DataAvailabilityResult(
            available=available,
            fresh=all_fresh,
            missing=missing,
            stale=stale,
            last_updated=last_updated,
        )

        logger.info(
            "Data availability check",
            extra={
                "match_id": match_id,
                "result": result.to_dict(),
            },
        )

        return result

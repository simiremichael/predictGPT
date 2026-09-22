"""SQLAlchemy models for leagues, seasons and provider mappings.

Every provider-specific record retains:
    provider_name  -- e.g. "api_football"
    provider_id    -- the ID as it appears in the provider's API
    internal_id    -- a UUID stable across providers
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import UUID, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class League(Base):
    __tablename__ = "leagues"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<League {self.name}>"


class Season(Base):
    __tablename__ = "seasons"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    league_id: Mapped[str] = mapped_column(String, ForeignKey("leagues.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    end_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class ProviderLeague(Base):
    """Maps an internal league to provider-specific IDs."""

    __tablename__ = "provider_leagues"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    internal_league_id: Mapped[str] = mapped_column(String, ForeignKey("leagues.id"), nullable=False, index=True)
    provider_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    provider_league_id: Mapped[str] = mapped_column(String(100), nullable=False)
    provider_season_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        # One row per (league, provider)
    )


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    short_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    slug: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True)
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    venue_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    venue_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class ProviderTeam(Base):
    """Maps an internal team to provider-specific IDs."""

    __tablename__ = "provider_teams"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    internal_team_id: Mapped[str] = mapped_column(String, ForeignKey("teams.id"), nullable=False, index=True)
    provider_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    provider_team_id: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

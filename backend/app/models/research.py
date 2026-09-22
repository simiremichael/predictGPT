"""SQLAlchemy models for web research and AI evidence.

These tables store:
- web_sources: normalized source metadata (extends the existing WebSource)
- research_runs: metadata about when research was performed
- research_evidence: generic evidence records (injuries, suspensions, lineups, news)
- evidence_conflicts: conflicting claims from different sources

The design preserves the existing football provider injury/lineup tables
(Phase 2) for provider data. These evidence tables store web-sourced
information with traceability to research runs and source URLs.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base
from models.league import _uuid


class ResearchRun(Base):
    """Record of a research run for a match."""

    __tablename__ = "research_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    match_id: Mapped[str] = mapped_column(
        String, ForeignKey("matches.id"), nullable=False, index=True
    )
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    source_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    query_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="running")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    cutoff_datetime: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    data_quality: Mapped[float | None] = mapped_column(Float, nullable=True)

    __table_args__ = (
        Index("idx_research_runs_match_cutoff", "match_id", "cutoff_datetime"),
    )


class ResearchEvidence(Base):
    """Generic evidence record extracted from web sources.

    Stores structured evidence (injuries, suspensions, lineups, team news)
    with references to the research run and source URLs.
    """

    __tablename__ = "research_evidence"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    match_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("matches.id"), nullable=True, index=True
    )
    team_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("teams.id"), nullable=True, index=True
    )
    research_run_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("research_runs.id"), nullable=True, index=True
    )
    evidence_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )
    subject: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    claim: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_status: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    source_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    evidence_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    __table_args__ = (
        Index("idx_research_evidence_match_type", "match_id", "evidence_type"),
        Index("idx_research_evidence_subject", "subject"),
    )


class EvidenceConflict(Base):
    """Representation of conflicting evidence from different sources."""

    __tablename__ = "evidence_conflicts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    match_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("matches.id"), nullable=True, index=True
    )
    research_run_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("research_runs.id"), nullable=True, index=True
    )
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    claim_a: Mapped[str] = mapped_column(Text, nullable=False)
    claim_b: Mapped[str] = mapped_column(Text, nullable=False)
    source_a_id: Mapped[str] = mapped_column(String(255), nullable=False)
    source_b_id: Mapped[str] = mapped_column(String(255), nullable=False)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    __table_args__ = (
        Index("idx_evidence_conflicts_match", "match_id"),
    )


class WebSourceExtended(Base):
    """Extended web source metadata with content and scoring.

    This complements the existing ``web_sources`` table with additional
    fields needed by the research pipeline: content hash, credibility
    and freshness scores, and content source tracking.
    """

    __tablename__ = "web_sources_extended"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    url: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)
    url_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    publisher: Mapped[str | None] = mapped_column(String(255), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    source_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_source: Mapped[str] = mapped_column(
        String(50), nullable=False, default="search_result_snippet"
    )
    credibility_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    freshness_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    match_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("matches.id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    __table_args__ = (
        Index("idx_web_sources_extended_match", "match_id"),
        Index("idx_web_sources_extended_type_score", "source_type", "credibility_score"),
    )

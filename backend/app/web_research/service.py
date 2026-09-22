"""Match research service.

Orchestrates the full web research pipeline:
1. Generate search queries for the match
2. Execute searches via the search provider abstraction
3. Retrieve source content
4. Deduplicate sources
5. Score credibility and freshness
6. Extract structured evidence via the AI provider
7. Detect conflicts
8. Return a MatchResearchResult

All web research is independent from the football data providers
(API-Football and Sportmonks). The service consumes normalized internal
models only.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from core.config import get_settings
from core.logging import get_logger
from web_research.base import WebSearchProvider
from web_research.deduplicator import deduplicate_sources
from web_research.exceptions import SearchProviderError, WebResearchError
from web_research.queries import MatchContext, MatchResearchQueryBuilder
from web_research.schemas import (
    EvidenceConflict,
    InjuryEvidence,
    LineupEvidence,
    MatchResearchResult,
    ResearchSource,
    SourceType,
    SuspensionEvidence,
    TeamNewsEvidence,
)
from web_research.sources import (
    calculate_freshness,
    normalize_search_result,
)

logger = get_logger(__name__)


class MatchResearchService:
    """Service for researching a specific football match via web search."""

    def __init__(
        self,
        search_provider: WebSearchProvider | None = None,
        ai_service: Any = None,
        redis_client: Any = None,
    ) -> None:
        self._settings = get_settings()
        self._search_provider = search_provider
        self._ai_service = ai_service
        self._redis = redis_client
        self._query_builder = MatchResearchQueryBuilder()

    async def get_search_provider(self) -> WebSearchProvider:
        """Get or lazily initialize the search provider."""
        if self._search_provider is None:
            from web_research.search import DuckDuckGoSearchProvider

            self._search_provider = DuckDuckGoSearchProvider()
        return self._search_provider

    async def research_match(
        self,
        match_id: str,
        home_team: str,
        away_team: str,
        competition: str | None = None,
        kickoff_at: datetime | None = None,
        cutoff_datetime: datetime | None = None,
        force_refresh: bool = False,
    ) -> MatchResearchResult:
        """Research a match and return structured evidence.

        Args:
            match_id: Internal match UUID.
            home_team: Home team name.
            away_team: Away team name.
            competition: Competition/league name.
            kickoff_at: Match kickoff time.
            cutoff_datetime: For backtesting - only use sources published before this.
            force_refresh: Bypass cache.

        Returns:
            MatchResearchResult with all collected evidence.
        """
        context = MatchContext(
            match_id=match_id,
            home_team=home_team,
            away_team=away_team,
            competition=competition,
            kickoff_at=kickoff_at.isoformat() if kickoff_at else None,
        )

        # Check cache
        cache_key = f"research:{match_id}:{cutoff_datetime.isoformat() if cutoff_datetime else 'live'}"
        if not force_refresh and self._redis:
            try:
                cached = await self._redis.get_json(cache_key)
                if cached:
                    return MatchResearchResult(**cached)
            except Exception:
                pass

        # Generate queries
        queries = self._query_builder.build_match_queries(context)

        # Collect sources from all queries
        sources: list[ResearchSource] = []
        for query_name, query_str, priority in queries:
            try:
                provider = await self.get_search_provider()
                raw_results = await provider.search(query_str, limit=5)

                for raw in raw_results:
                    source = normalize_search_result(
                        title=raw.title,
                        url=raw.url,
                        snippet=raw.snippet,
                        publisher=raw.publisher,
                        published_at=raw.published_at,
                        credibility_enabled=self._settings.source_credibility_enabled,
                    )
                    sources.append(source)
            except Exception as exc:
                logger.warning(
                    "Search failed for query",
                    extra={"query": query_str, "error": str(exc)},
                )
                continue

        # Deduplicate
        sources = deduplicate_sources(sources)

        # Filter by cutoff for backtesting
        if cutoff_datetime is not None:
            sources = self._filter_by_cutoff(sources, cutoff_datetime)

        # Calculate freshness
        for source in sources:
            source.freshness_score = calculate_freshness(
                published_at=source.published_at,
                retrieved_at=source.retrieved_at,
                match_kickoff=kickoff_at,
                info_type="news",
            )

        # Extract evidence from sources with content
        injuries: list[InjuryEvidence] = []
        suspensions: list[SuspensionEvidence] = []
        lineups: list[LineupEvidence] = []
        team_news: list[TeamNewsEvidence] = []

        if self._ai_service:
            for source in sources:
                content = await self._retrieve_source_content(source)
                if not content:
                    continue

                try:
                    inj = await self._ai_service.extract_injuries(
                        content, source.url, home_team, away_team
                    )
                    injuries.extend(inj)

                    susp = await self._ai_service.extract_suspensions(
                        content, source.url, home_team, away_team
                    )
                    suspensions.extend(susp)

                    lineup = await self._ai_service.extract_lineup(
                        content, source.url, home_team, away_team
                    )
                    if lineup:
                        lineups.append(lineup)

                    news = await self._ai_service.extract_team_news(
                        content, source.url, home_team, away_team
                    )
                    team_news.extend(news)
                except Exception as exc:
                    logger.warning(
                        "Evidence extraction failed for source",
                        extra={"url": source.url, "error": str(exc)},
                    )

        # Detect conflicts
        conflicts = await self._detect_conflicts(
            injuries, suspensions, lineups, team_news, sources
        )

        # Calculate data quality
        data_quality = self._calculate_data_quality(
            sources, injuries, suspensions, lineups, team_news
        )

        result = MatchResearchResult(
            match_id=match_id,
            researched_at=datetime.now(timezone.utc),
            sources=sources,
            injuries=injuries,
            suspensions=suspensions,
            lineups=lineups,
            team_news=team_news,
            conflicts=conflicts,
            data_quality=data_quality,
        )

        # Cache result
        if self._redis:
            ttl = self._settings.redis_cache_ttl_default
            try:
                await self._redis.set_json(cache_key, result.model_dump(), ttl=ttl)
            except Exception:
                pass

        return result

    async def _retrieve_source_content(self, source: ResearchSource) -> str | None:
        """Retrieve full content from a source URL."""
        from web_research.parser import fetch_url_content, sanitize_for_ai

        if source.content_source == "retrieved_article_content" and source.content:
            return source.content

        raw = fetch_url_content(source.url)
        if raw:
            content = sanitize_for_ai(raw)
            source.content = content
            source.content_source = "retrieved_article_content"
            return content
        return None

    def _filter_by_cutoff(
        self, sources: list[ResearchSource], cutoff: datetime
    ) -> list[ResearchSource]:
        """Filter sources to only those published before the cutoff."""
        if cutoff.tzinfo is None:
            cutoff = cutoff.replace(tzinfo=timezone.utc)

        filtered: list[ResearchSource] = []
        for source in sources:
            if source.published_at is None:
                # If no publish date, keep it but mark with low freshness
                source.freshness_score = min(source.freshness_score, 0.3)
                filtered.append(source)
                continue

            pub_time = source.published_at
            if pub_time.tzinfo is None:
                pub_time = pub_time.replace(tzinfo=timezone.utc)

            if pub_time <= cutoff:
                filtered.append(source)
        return filtered

    async def _detect_conflicts(
        self,
        injuries: list[InjuryEvidence],
        suspensions: list[SuspensionEvidence],
        lineups: list[LineupEvidence],
        team_news: list[TeamNewsEvidence],
        sources: list[ResearchSource],
    ) -> list[EvidenceConflict]:
        """Detect conflicts in extracted evidence."""
        if not self._ai_service:
            return []

        # Build evidence text for conflict detection
        evidence_parts: list[str] = []
        for inj in injuries:
            evidence_parts.append(
                f"Injury: {inj.player} ({inj.team or 'unknown team'}) "
                f"status={inj.status} evidence={inj.evidence_status} "
                f"sources={inj.source_ids}"
            )
        for susp in suspensions:
            evidence_parts.append(
                f"Suspension: {susp.player} ({susp.team or 'unknown team'}) "
                f"status={susp.suspension_status} evidence={susp.evidence_status} "
                f"sources={susp.source_ids}"
            )
        for lineup in lineups:
            evidence_parts.append(
                f"Lineup: {lineup.team} status={lineup.status} "
                f"sources={lineup.source_ids}"
            )
        for news in team_news:
            evidence_parts.append(
                f"News: {news.team} type={news.news_type} "
                f"evidence={news.evidence_status} sources={news.source_ids}"
            )

        evidence_text = "\n".join(evidence_parts)
        if not evidence_text:
            return []

        raw_conflicts = await self._ai_service.detect_conflicts(
            evidence_text, "", ""
        )

        conflicts: list[EvidenceConflict] = []
        for c in raw_conflicts:
            try:
                conflicts.append(EvidenceConflict(**c))
            except Exception:
                pass

        return conflicts

    def _calculate_data_quality(
        self,
        sources: list[ResearchSource],
        injuries: list[InjuryEvidence],
        suspensions: list[SuspensionEvidence],
        lineups: list[LineupEvidence],
        team_news: list[TeamNewsEvidence],
    ) -> float:
        """Calculate overall research data quality (0.0 - 1.0)."""
        if not sources:
            return 0.0

        # Source quality: credibility and freshness
        source_quality = sum(
            s.credibility_score * s.freshness_score for s in sources
        ) / len(sources)

        # Coverage: how much evidence was extracted
        evidence_count = len(injuries) + len(suspensions) + len(lineups) + len(team_news)
        coverage = min(1.0, evidence_count / 10)

        # Confirmed evidence weight
        confirmed_count = sum(
            1 for e in injuries + suspensions + lineups + team_news
            if getattr(e, "evidence_status", None) == "confirmed"
        )
        confidence_weight = min(1.0, confirmed_count / 5) if confirmed_count > 0 else 0.0

        quality = source_quality * 0.5 + coverage * 0.3 + confidence_weight * 0.2
        return round(quality, 4)

    async def close(self) -> None:
        """Close provider connections."""
        if self._search_provider:
            await self._search_provider.close()
        if self._ai_service:
            await self._ai_service.close()
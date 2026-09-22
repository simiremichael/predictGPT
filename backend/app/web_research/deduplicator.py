"""Source deduplication.

Detects and removes duplicate sources based on:
- Normalized URL matching
- Content hash comparison
- Title similarity

Duplicates can occur from:
- Same URL appearing in multiple search results
- Same article syndicated across multiple sites
- Search snippets repeating the same story
"""
from __future__ import annotations

import hashlib
from difflib import SequenceMatcher
from typing import Any

from web_research.schemas import ResearchSource
from web_research.sources import content_hash, normalize_url


def _title_similarity(title_a: str | None, title_b: str | None) -> float:
    """Calculate similarity ratio between two titles (0.0 - 1.0)."""
    if not title_a or not title_b:
        return 0.0
    return SequenceMatcher(None, title_a.lower(), title_b.lower()).ratio()


def deduplicate_sources(
    sources: list[ResearchSource],
    url_threshold: float = 0.95,
    content_threshold: float = 0.90,
    title_threshold: float = 0.85,
) -> list[ResearchSource]:
    """Remove duplicate sources from a list.

    Deduplicates based on:
    1. Exact normalized URL match (strongest)
    2. Content hash match
    3. Title + publisher similarity (when URLs differ but content is the same)

    Keeps the first occurrence of each unique source.
    """
    if not sources:
        return []

    seen_urls: dict[str, ResearchSource] = {}
    seen_hashes: dict[str, ResearchSource] = {}
    unique_sources: list[ResearchSource] = []

    for source in sources:
        normalized_url = normalize_url(source.url)

        # Check URL match
        if normalized_url in seen_urls:
            continue

        # Check content hash match
        if source.content:
            ch = content_hash(source.content)
            if ch in seen_hashes:
                continue
            seen_hashes[ch] = source

        # Check title similarity for likely syndicated articles
        is_duplicate_title = False
        for existing in unique_sources:
            if source.publisher == existing.publisher:
                sim = _title_similarity(source.title, existing.title)
                if sim >= title_threshold:
                    is_duplicate_title = True
                    break

        if is_duplicate_title:
            continue

        seen_urls[normalized_url] = source
        unique_sources.append(source)

    return unique_sources


def compute_source_hash(source: ResearchSource) -> str:
    """Generate a hash for a ResearchSource for caching/dedup lookup."""
    raw = f"{normalize_url(source.url)}|{source.title or ''}|{source.publisher or ''}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]

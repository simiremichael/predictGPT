"""Tests for source deduplication."""
from __future__ import annotations

from web_research.schemas import ResearchSource, SourceType
from web_research.deduplicator import (
    compute_source_hash,
    deduplicate_sources,
)


class TestDeduplicateSources:
    def test_removes_exact_url_duplicates(self) -> None:
        sources = [
            ResearchSource(url="https://example.com/article", title="Test", credibility_score=0.8, freshness_score=0.9),
            ResearchSource(url="https://example.com/article", title="Test", credibility_score=0.8, freshness_score=0.9),
        ]
        result = deduplicate_sources(sources)
        assert len(result) == 1

    def test_removes_normalized_url_duplicates(self) -> None:
        sources = [
            ResearchSource(url="https://www.example.com/article", title="Test", credibility_score=0.8, freshness_score=0.9),
            ResearchSource(url="https://example.com/article", title="Test", credibility_score=0.8, freshness_score=0.9),
        ]
        result = deduplicate_sources(sources)
        assert len(result) == 1

    def test_different_urls_kept(self) -> None:
        sources = [
            ResearchSource(url="https://example.com/article1", title="Test 1", credibility_score=0.8, freshness_score=0.9),
            ResearchSource(url="https://example.com/article2", title="Test 2", credibility_score=0.7, freshness_score=0.8),
        ]
        result = deduplicate_sources(sources)
        assert len(result) == 2

    def test_removes_content_hash_duplicates(self) -> None:
        content = "This is a long article content that is the same"
        sources = [
            ResearchSource(url="https://site1.com/article", title="Test", content=content, credibility_score=0.8, freshness_score=0.9),
            ResearchSource(url="https://site2.com/article", title="Same Test", content=content, credibility_score=0.7, freshness_score=0.8),
        ]
        result = deduplicate_sources(sources)
        assert len(result) == 1

    def test_empty_list(self) -> None:
        result = deduplicate_sources([])
        assert result == []

    def test_similar_titles_same_publisher_deduplicated(self) -> None:
        sources = [
            ResearchSource(url="https://a.com/1", title="Breaking: Team News", publisher="Sky Sports", credibility_score=0.8, freshness_score=0.9, source_type=SourceType.SPORTS_MEDIA),
            ResearchSource(url="https://b.com/2", title="Breaking: Team News", publisher="Sky Sports", credibility_score=0.7, freshness_score=0.8, source_type=SourceType.SPORTS_MEDIA),
        ]
        result = deduplicate_sources(sources)
        assert len(result) == 1


class TestComputeSourceHash:
    def test_same_source_same_hash(self) -> None:
        s = ResearchSource(url="https://example.com/article", title="Test", publisher="Test Publisher", credibility_score=0.8, freshness_score=0.9)
        h1 = compute_source_hash(s)
        h2 = compute_source_hash(s)
        assert h1 == h2

    def test_different_source_different_hash(self) -> None:
        s1 = ResearchSource(url="https://example.com/1", title="Test", publisher="Test", credibility_score=0.8, freshness_score=0.9)
        s2 = ResearchSource(url="https://example.com/2", title="Test", publisher="Test", credibility_score=0.8, freshness_score=0.9)
        assert compute_source_hash(s1) != compute_source_hash(s2)

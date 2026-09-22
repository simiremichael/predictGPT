"""Tests for source credibility, freshness, and normalization."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from web_research.schemas import ResearchSource, SourceType
from web_research.sources import (
    calculate_credibility,
    calculate_freshness,
    classify_source_type,
    content_hash,
    normalize_search_result,
    normalize_url,
)


class TestSourceTypeClassification:
    def test_official_team_detected(self) -> None:
        url = "https://www.arsenal.com/news/match-preview"
        stype = classify_source_type(url)
        assert stype == SourceType.OFFICIAL_TEAM

    def test_social_media_detected(self) -> None:
        url = "https://twitter.com/footballnews/status/123"
        stype = classify_source_type(url)
        assert stype == SourceType.SOCIAL_MEDIA

    def test_blog_detected(self) -> None:
        url = "https://myfootballblog.com/post"
        stype = classify_source_type(url)
        assert stype == SourceType.BLOG

    def test_unknown_source(self) -> None:
        url = "https://random-site-12345.com/article"
        stype = classify_source_type(url)
        assert stype == SourceType.UNKNOWN


class TestCredibilityScoring:
    def test_official_source_high_credibility(self) -> None:
        score = calculate_credibility(
            url="https://www.arsenal.com/news",
            source_type=SourceType.OFFICIAL_TEAM,
        )
        assert score >= 0.9

    def test_reputable_news_medium_high(self) -> None:
        score = calculate_credibility(
            url="https://www.bbc.com/sport/football",
            source_type=SourceType.REPUTABLE_NEWS,
        )
        assert 0.7 <= score <= 1.0

    def test_unknown_source_low(self) -> None:
        score = calculate_credibility(
            url="https://unknown-blog.com",
            source_type=SourceType.UNKNOWN,
        )
        assert score <= 0.5

    def test_credibility_disabled(self) -> None:
        score = calculate_credibility(
            url="https://www.arsenal.com/news",
            source_type=SourceType.OFFICIAL_TEAM,
            enabled=False,
        )
        assert score == 0.5


class TestFreshnessScoring:
    def test_recent_source_high_freshness(self) -> None:
        now = datetime.now(timezone.utc)
        published = now - timedelta(hours=2)
        score = calculate_freshness(published, now)
        assert score > 0.8

    def test_old_source_low_freshness(self) -> None:
        now = datetime.now(timezone.utc)
        published = now - timedelta(days=30)
        score = calculate_freshness(published, now)
        assert score < 0.3

    def test_no_published_date(self) -> None:
        now = datetime.now(timezone.utc)
        score = calculate_freshness(None, now)
        assert score == 0.3

    def test_post_kickoff_low_freshness(self) -> None:
        now = datetime.now(timezone.utc)
        kickoff = now - timedelta(hours=2)
        published = now - timedelta(hours=1)
        score = calculate_freshness(published, now, match_kickoff=kickoff)
        assert score < 0.5

    def test_pre_kickoff_increased_freshness(self) -> None:
        now = datetime.now(timezone.utc)
        kickoff = now + timedelta(hours=3)
        published = now - timedelta(hours=1)
        score = calculate_freshness(published, now, match_kickoff=kickoff)
        assert score > 0.8


class TestURLNormalization:
    def test_www_stripped(self) -> None:
        normalized = normalize_url("https://www.example.com/path")
        assert "www." not in normalized

    def test_tracking_params_removed(self) -> None:
        url = "https://example.com/path?utm_source=google&param=value"
        normalized = normalize_url(url)
        assert "utm_source" not in normalized
        assert "param=value" in normalized

    def test_trailing_slash_removed(self) -> None:
        normalized = normalize_url("https://example.com/path/")
        assert not normalized.endswith("/")


class TestContentHashing:
    def test_same_content_same_hash(self) -> None:
        h1 = content_hash("hello world")
        h2 = content_hash("hello world")
        assert h1 == h2

    def test_different_content_different_hash(self) -> None:
        h1 = content_hash("hello world")
        h2 = content_hash("goodbye world")
        assert h1 != h2

    def test_whitespace_ignored(self) -> None:
        h1 = content_hash("hello world")
        h2 = content_hash("  hello world  ")
        assert h1 == h2


class TestNormalizeSearchResult:
    def test_basic_normalization(self) -> None:
        source = normalize_search_result(
            title="Test Article",
            url="https://bbc.com/sport/football",
            snippet="This is a test",
            publisher="BBC Sport",
        )
        assert source.url == "https://bbc.com/sport/football"
        assert source.title == "Test Article"
        assert source.publisher == "BBC Sport"
        assert 0.0 <= source.credibility_score <= 1.0
        assert 0.0 <= source.freshness_score <= 1.0
        assert source.content_source == "search_result_snippet"

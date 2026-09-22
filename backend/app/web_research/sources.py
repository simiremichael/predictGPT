"""Source normalization, credibility scoring, and freshness calculation.

Provides deterministic scoring for source reliability based on publisher
metadata and publication recency. All rules are configurable.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from web_research.schemas import ResearchSource, SourceType


# Publisher credibility tiers - publishers in each tier get the listed credibility.
# These are real-world sports publishers; the rules are transparent and
# configurable.
CREDIBILITY_TIERS: dict[str, float] = {
    # Official sources - highest credibility
    "premierleague.com": 1.0,
    "fcbarcelona.com": 1.0,
    "realmadrid.com": 1.0,
    "arsenal.com": 1.0,
    "chelsea.com": 1.0,
    "liverpool.com": 1.0,
    "manchesterunited.com": 1.0,
    "manchestercity.com": 1.0,
    "espn.com": 0.9,
    "bbc.com": 0.9,
    "sky.com": 0.9,
    "sky sports": 0.9,
    "the guardian": 0.9,
    "bloomberg": 0.9,
    # Reputable sports publications - high credibility
    "espnfc.com": 0.9,
    "theathletic.com": 0.9,
    "fourfourtwo.com": 0.8,
    "goal.com": 0.8,
    "dlacrx": 0.0,
}


def classify_source_type(url: str, publisher: str | None = None) -> SourceType:
    """Classify a source URL into a source type based on its domain.

    Classification is based on known official domains and publisher patterns.
    Unknown sources are classified as UNKNOWN rather than assumed credible.
    """
    parsed = urlparse(url)
    domain = parsed.netloc.lower().removeprefix("www.")

    # Official team/league sites
    official_teams = {
        "premierleague.com",
        "arsenal.com",
        "chelsea.com",
        "liverpool.com",
        "manchesterunited.com",
        "manchestercity.com",
        "realmadrid.com",
        "fcbarcelona.com",
        "acmilan.com",
        "juventus.com",
        "borussia.de",
        "bayern.de",
        "psg.fr",
    }

    if any(domain.endswith(tld) for tld in [".com", ".org", ".co.uk", ".eu", ".fr", ".de", ".it", ".es"]):
        if domain in official_teams:
            return SourceType.OFFICIAL_TEAM
        if "premierleague" in domain or "laliga" in domain or "seriea" in domain:
            return SourceType.OFFICIAL_COMPETITION
        if "league" in domain and domain.endswith(".com"):
            return SourceType.OFFICIAL_LEAGUE

    publisher_lower = (publisher or "").lower()
    if "sky sports" in publisher_lower:
        return SourceType.REPUTABLE_NEWS
    if "bbc" in publisher_lower:
        return SourceType.REPUTABLE_NEWS
    if "the athletic" in publisher_lower or "the guardian" in publisher_lower:
        return SourceType.REPUTABLE_NEWS
    if publisher_lower and "journalist" in publisher_lower:
        return SourceType.JOURNALIST
    if "twitter.com" in url or "x.com" in url:
        return SourceType.SOCIAL_MEDIA
    if "reddit.com" in url or "blog" in domain:
        return SourceType.BLOG

    return SourceType.UNKNOWN


def calculate_credibility(
    url: str,
    publisher: str | None = None,
    source_type: SourceType | None = None,
    content: str | None = None,
    enabled: bool = True,
) -> float:
    """Calculate a credibility score (0.0 - 1.0) for a source.

    Scoring is transparent:
    - Official sources: 0.95-1.0
    - Established reputable publications: 0.8-0.95
    - Recognized journalists: 0.7-0.85
    - General sports websites: 0.5-0.7
    - Unknown/unverified: 0.1-0.5

    Does NOT invent credibility. Returns a conservative default for unknown sources.
    """
    if not enabled:
        return 0.5

    if source_type is None:
        source_type = classify_source_type(url, publisher)

    # Type-based base score
    type_scores = {
        SourceType.OFFICIAL_TEAM: 0.95,
        SourceType.OFFICIAL_LEAGUE: 0.95,
        SourceType.OFFICIAL_COMPETITION: 0.95,
        SourceType.REPUTABLE_NEWS: 0.85,
        SourceType.SPORTS_MEDIA: 0.7,
        SourceType.JOURNALIST: 0.75,
        SourceType.SEARCH_RESULT: 0.4,
        SourceType.SOCIAL_MEDIA: 0.25,
        SourceType.BLOG: 0.3,
        SourceType.UNKNOWN: 0.1,
    }

    score = type_scores.get(source_type, 0.1)

    # Publisher-specific adjustment
    publisher_lower = (publisher or "").lower()
    parsed = urlparse(url)
    domain = parsed.netloc.lower().removeprefix("www.")

    for pub_key, pub_score in CREDIBILITY_TIERS.items():
        if pub_key in publisher_lower or pub_key in domain:
            score = max(score, pub_score)

    # Content quality hint: sources with substantial content
    if content and len(content) > 500:
        score = min(1.0, score + 0.05)

    return round(score, 4)


def normalize_url(url: str) -> str:
    """Normalize a URL for deduplication comparison.

    Strips tracking parameters, fragments, and www prefix.
    """
    parsed = urlparse(url)
    scheme = parsed.scheme or "https"
    netloc = parsed.netloc.lower()
    # Remove www prefix
    if netloc.startswith("www."):
        netloc = netloc[4:]

    # Strip common tracking parameters
    query = parsed.query
    if query:
        params = []
        for pair in query.split("&"):
            if "=" in pair:
                key, _ = pair.split("=", 1)
                if key.lower() in {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "fbclid"}:
                    continue
            params.append(pair)
        query = "&".join(params)

    path = parsed.path.rstrip("/")

    return f"{scheme}://{netloc}{path}?{query}" if query else f"{scheme}://{netloc}{path}"


def content_hash(text: str) -> str:
    """Generate a SHA-256 hash of content for deduplication."""
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()[:32]


def calculate_freshness(
    published_at: datetime | None,
    retrieved_at: datetime,
    match_kickoff: datetime | None = None,
    info_type: str = "news",
) -> float:
    """Calculate a freshness score (0.0 - 1.0) for a source.

    More recent sources relative to the match kickoff receive higher scores.
    Information published after the match has started receives a low score
    (important for backtesting cutoffs).

    Args:
        published_at: When the source content was published.
        retrieved_at: When the source was retrieved.
        match_kickoff: When the match kicks off.
        info_type: Type of information (injury, lineup, news, etc.).
    """
    if published_at is None:
        return 0.3

    now = retrieved_at
    age_seconds = (now - published_at).total_seconds()

    if age_seconds < 0:
        # Published in the future - should not happen, low trust
        return 0.1

    # Decay based on age - newer = fresher
    age_hours = age_seconds / 3600

    if age_hours < 1:
        age_score = 1.0
    elif age_hours < 6:
        age_score = 0.9
    elif age_hours < 12:
        age_score = 0.8
    elif age_hours < 24:
        age_score = 0.7
    elif age_hours < 48:
        age_score = 0.5
    elif age_hours < 120:
        age_score = 0.3
    else:
        age_score = 0.1

    # If we have match kickoff, score relative to it
    if match_kickoff is not None:
        time_to_kickoff = (match_kickoff - published_at).total_seconds()
        time_to_kickoff_hours = time_to_kickoff / 3600

        if time_to_kickoff < 0:
            # Published after kickoff
            age_score *= 0.2
        elif time_to_kickoff_hours < 6:
            # Published shortly before kickoff - very relevant
            age_score = max(age_score, 0.85)
        elif time_to_kickoff_hours < 24:
            age_score = max(age_score, 0.7)
        elif time_to_kickoff_hours < 72:
            age_score = max(age_score, 0.5)

    # Injury/lineup info depreciates faster than general news
    if info_type in ("injury", "lineup", "suspension", "availability"):
        age_score *= 0.9

    return round(max(0.0, min(1.0, age_score)), 4)


def normalize_search_result(
    title: str | None,
    url: str,
    snippet: str | None,
    publisher: str | None = None,
    published_at: str | None = None,
    credibility_enabled: bool = True,
) -> ResearchSource:
    """Normalize a raw search result into a ResearchSource."""
    source_type = classify_source_type(url, publisher)
    normalized_url = normalize_url(url)

    pub_dt: datetime | None = None
    if published_at:
        try:
            from dateutil import parser as date_parser

            pub_dt = date_parser.parse(published_at)
        except Exception:
            pass

    retrieved_at = datetime.now(timezone.utc)

    credibility = calculate_credibility(
        url=normalized_url,
        publisher=publisher,
        source_type=source_type,
        enabled=credibility_enabled,
    )

    freshness = calculate_freshness(
        published_at=pub_dt,
        retrieved_at=retrieved_at,
        info_type="news",
    )

    return ResearchSource(
        url=normalized_url,
        title=title,
        publisher=publisher,
        published_at=pub_dt,
        retrieved_at=retrieved_at,
        source_type=source_type,
        snippet=snippet,
        credibility_score=credibility,
        freshness_score=freshness,
        content_source="search_result_snippet",
    )

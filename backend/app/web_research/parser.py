"""HTML/text parsing and sanitization for web content.

This module treats all web content as untrusted input.  It sanitizes
HTML to remove script tags, iframes, tracking elements, and embedded
instructions before the content is sent to the AI provider.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any


class _TextExtractor(HTMLParser):
    """Extract visible text from HTML, skipping script/style/iframe content."""

    _SKIP_TAGS = {"script", "style", "iframe", "noscript", "template", "head"}

    def __init__(self) -> None:
        super().__init__()
        self._text_parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in self._SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self._SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            stripped = data.strip()
            if stripped:
                self._text_parts.append(stripped)

    def get_text(self) -> str:
        return "\n".join(self._text_parts)


def sanitize_html(html: str, max_length: int = 50000) -> str:
    """Sanitize HTML content for safe AI processing.

    Removes:
    - script, style, iframe, noscript, template tags and their content
    - HTML comments
    - Tracking pixels and embeds
    - Embedded JavaScript instructions (onclick, onload, etc.)

    Returns clean text content.
    """
    if not html:
        return ""

    # Remove HTML comments
    html = re.sub(r"<!--.*?-->", "", html, flags=re.DOTALL)

    # Extract text using parser (handles malformed HTML gracefully)
    parser = _TextExtractor()
    try:
        parser.feed(html)
    except Exception:
        pass

    text = parser.get_text()

    # Remove remaining script-like patterns
    text = re.sub(
        r"(?i)(?:javascript|vbscript|data:text/html|onclick|onload|onerror|onmouseover)",
        "",
        text,
    )

    # Collapse whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()

    if len(text) > max_length:
        text = text[:max_length]

    return text


def sanitize_for_ai(content: str, max_length: int = 20000) -> str:
    """Full sanitization pipeline for content sent to AI.

    Strips HTML, removes potential instruction-injection patterns,
    and truncates to a maximum length.
    """
    # First strip HTML
    text = sanitize_html(content, max_length=max_length)

    # Remove potential prompt injection markers
    injection_patterns = [
        r"(?i)ignore (?:previous |prior )?instructions",
        r"(?i)disregard (?:previous |prior )?instructions",
        r"(?i)override (?:previous |prior )?instructions",
        r"(?i)system prompt",
        r"(?i)you are (?:now )?a different",
        r"(?i)pretend you are",
        r"(?i)act as if",
    ]

    for pattern in injection_patterns:
        text = re.sub(pattern, "[FILTERED]", text)

    if len(text) > max_length:
        text = text[:max_length]

    return text


def extract_title(html: str) -> str | None:
    """Extract the title from HTML content."""
    if not html:
        return None

    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if match:
        title = match.group(1).strip()
        title = re.sub(r"\s+", " ", title)
        return title or None
    return None


def extract_publisher(html: str, url: str) -> str | None:
    """Try to extract the publisher name from HTML meta tags."""
    # Check meta property="og:site_name"
    match = re.search(
        r'<meta[^>]+property=["\']?og:site_name["\']?[^>]*content=["\']([^"\']+)["\']',
        html,
        re.IGNORECASE,
    )
    if match:
        return match.group(1).strip()

    # Check meta name="author"
    match = re.search(
        r'<meta[^>]+name=["\']?author["\']?[^>]*content=["\']([^"\']+)["\']',
        html,
        re.IGNORECASE,
    )
    if match:
        return match.group(1).strip()

    # Try domain as fallback
    from urllib.parse import urlparse

    domain = urlparse(url).netloc.replace("www.", "")
    if domain:
        return domain

    return None


def fetch_url_content(url: str, timeout: float = 15.0) -> str | None:
    """Fetch the full content of a URL.

    Returns None if the content cannot be retrieved.
    """
    import httpx

    try:
        headers = {
            "User-Agent": "FootballAI/1.0 (research-bot; contact@example.com)",
            "Accept": "text/html,application/xhtml+xml",
        }
        with httpx.Client(timeout=httpx.Timeout(timeout), headers=headers, follow_redirects=True) as client:
            resp = client.get(url)
            if resp.status_code == 200:
                return resp.text
    except Exception:
        pass
    return None

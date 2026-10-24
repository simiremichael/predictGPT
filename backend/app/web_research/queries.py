"""Match-specific and team-specific search query generation.

Generates targeted, non-exhaustive search queries for a given match.
Query templates are configurable via settings.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class MatchContext:
    """Context needed to generate search queries for a match."""

    match_id: str
    home_team: str
    away_team: str
    competition: str | None = None
    kickoff_at: str | None = None
    season: str | None = None


@dataclass
class QueryTemplate:
    """Template for a search query."""

    name: str
    template: str
    category: str
    priority: int = 10


# Default query templates - configurable via settings
DEFAULT_QUERY_TEMPLATES: list[QueryTemplate] = [
    QueryTemplate(
        name="injury_news",
        template="{home_team} {away_team} {competition} injury injuries unavailable players suspensions bans",
        category="injury",
        priority=10,
    ),
    QueryTemplate(
        name="predicted_lineup",
        template="{home_team} vs {away_team} {competition} predicted lineup team news",
        category="lineup",
        priority=9,
    ),
    QueryTemplate(
        name="formation_analysis",
        template=(
            "{home_team} vs {away_team} {competition} "
            "expected formation tactical setup match preview {kickoff_at}"
        ),
        category="lineup",
        priority=7,
    ),
    QueryTemplate(
        name="match_preview",
        template="{home_team} vs {away_team} {competition} match preview head to head",
        category="preview",
        priority=8,
    ),
    QueryTemplate(
        name="recent_form",
        template=(
            "{home_team} {away_team} {competition} recent form last results "
            "league standings season goals scored conceded xG before {kickoff_at}"
        ),
        category="form",
        priority=8,
    ),
    QueryTemplate(
        name="home_team_form",
        template=(
            "{home_team} latest results recent form goals scored conceded "
            "{competition} {season} before {kickoff_at}"
        ),
        category="recent_form",
        priority=7,
    ),
    QueryTemplate(
        name="away_team_form",
        template=(
            "{away_team} latest results recent form goals scored conceded "
            "{competition} {season} before {kickoff_at}"
        ),
        category="recent_form",
        priority=7,
    ),
    QueryTemplate(
        name="home_team_news",
        template=(
            "{home_team} team news form injuries predicted lineup manager comments "
            "{competition} {kickoff_at}"
        ),
        category="recent_form",
        priority=6,
    ),
    QueryTemplate(
        name="away_team_news",
        template=(
            "{away_team} team news form injuries predicted lineup manager comments "
            "{competition} {kickoff_at}"
        ),
        category="recent_form",
        priority=6,
    ),
    QueryTemplate(
        name="match_result_history",
        template=(
            "{home_team} vs {away_team} previous meetings head to head results "
            "{competition}"
        ),
        category="head_to_head",
        priority=6,
    ),
    QueryTemplate(
        name="home_team_standings",
        template=(
            "{home_team} {competition} {season} league table position points "
            "goals for against"
        ),
        category="league_standings",
        priority=5,
    ),
    QueryTemplate(
        name="away_team_standings",
        template=(
            "{away_team} {competition} {season} league table position points "
            "goals for against"
        ),
        category="league_standings",
        priority=5,
    ),
    QueryTemplate(
        name="home_official_site_discovery",
        template='"{home_team}" official website club',
        category="official_site_discovery",
        priority=5,
    ),
    QueryTemplate(
        name="away_official_site_discovery",
        template='"{away_team}" official website club',
        category="official_site_discovery",
        priority=5,
    ),
]


class MatchResearchQueryBuilder:
    """Generates search queries for a specific match.

    A curated set of match and team queries covers the key information
    categories without generating an unbounded number of searches.
    """

    def __init__(self, templates: list[QueryTemplate] | None = None) -> None:
        self._templates = templates or DEFAULT_QUERY_TEMPLATES

    def build_queries(
        self,
        context: MatchContext,
        categories: set[str] | None = None,
    ) -> list[tuple[str, str, int]]:
        """Build search queries for the given match context.

        Args:
            context: Match context with team names, competition, etc.
            categories: If provided, only include templates in these categories.

        Returns:
            List of (query_name, query_string, priority) tuples, sorted by priority.
        """
        vars_dict = self._build_template_vars(context)
        queries: list[tuple[str, str, int]] = []

        for template in self._templates:
            if categories and template.category not in categories:
                continue
            query_string = " ".join(template.template.format(**vars_dict).split())
            queries.append((template.name, query_string, template.priority))

        queries.sort(key=lambda x: (-x[2], x[0]))
        return queries

    def build_match_queries(
        self,
        context: MatchContext,
    ) -> list[tuple[str, str, int]]:
        """Build the full set of match queries."""
        return self.build_queries(context)

    def build_team_queries(
        self,
        team_name: str,
        competition: str | None = None,
        days_back: int = 3,
    ) -> list[tuple[str, str, int]]:
        """Build team-specific research queries."""
        queries: list[tuple[str, str, int]] = []

        team_templates = [
            (f"{team_name} injury news", "injury", 10),
            (f"{team_name} suspensions", "suspension", 10),
            (f"{team_name} predicted lineup", "lineup", 9),
            (f"{team_name} team news", "news", 8),
            (f"{team_name} latest injuries", "injury", 9),
            (f"{team_name} rotation", "news", 7),
            (f"{team_name} tactical change", "tactical", 6),
        ]

        for query_str, category, priority in team_templates:
            queries.append((category, query_str, priority))

        queries.sort(key=lambda x: (-x[2], x[0]))
        return queries

    @staticmethod
    def _build_template_vars(context: MatchContext) -> dict[str, Any]:
        """Build the variable dict for template formatting."""
        return {
            "home_team": context.home_team,
            "away_team": context.away_team,
            "competition": context.competition or "",
            "kickoff_at": context.kickoff_at or "",
            "season": context.season or "",
        }

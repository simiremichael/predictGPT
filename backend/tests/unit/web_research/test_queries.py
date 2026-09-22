"""Tests for web research query generation."""
from __future__ import annotations

from web_research.queries import MatchContext, MatchResearchQueryBuilder, QueryTemplate


class TestMatchResearchQueryBuilder:
    """Tests for query generation."""

    def test_build_queries_returns_list(self) -> None:
        builder = MatchResearchQueryBuilder()
        context = MatchContext(
            match_id="m1",
            home_team="Arsenal",
            away_team="Chelsea",
            competition="Premier League",
        )
        queries = builder.build_match_queries(context)
        assert len(queries) > 0
        assert all(len(q) == 3 for q in queries)

    def test_queries_contain_team_names(self) -> None:
        builder = MatchResearchQueryBuilder()
        context = MatchContext(
            match_id="m1",
            home_team="Arsenal",
            away_team="Chelsea",
            competition="Premier League",
        )
        queries = builder.build_queries(context, categories={"injury"})
        query_strings = [q[1] for q in queries]
        assert any("Arsenal" in q and "Chelsea" in q for q in query_strings)

    def test_category_filtering(self) -> None:
        builder = MatchResearchQueryBuilder()
        context = MatchContext(
            match_id="m1",
            home_team="Arsenal",
            away_team="Chelsea",
        )
        queries = builder.build_queries(context, categories={"injury"})
        assert len(queries) > 0
        assert all(len(q) == 3 for q in queries)
        # All queries should come from injury category templates
        for name, _, priority in queries:
            assert priority <= 10

    def test_priority_sorting(self) -> None:
        builder = MatchResearchQueryBuilder()
        context = MatchContext(
            match_id="m1",
            home_team="Arsenal",
            away_team="Chelsea",
        )
        queries = builder.build_queries(context)
        priorities = [q[2] for q in queries]
        assert priorities == sorted(priorities, reverse=True)

    def test_build_team_queries(self) -> None:
        builder = MatchResearchQueryBuilder()
        queries = builder.build_team_queries("Arsenal")
        assert len(queries) > 0
        query_strings = [q[1] for q in queries]
        assert any("Arsenal" in q for q in query_strings)

    def test_custom_templates(self) -> None:
        templates = [
            QueryTemplate(name="test", template="{home_team} vs {away_team}", category="test", priority=1),
        ]
        builder = MatchResearchQueryBuilder(templates=templates)
        context = MatchContext(
            match_id="m1",
            home_team="Arsenal",
            away_team="Chelsea",
        )
        queries = builder.build_queries(context)
        assert len(queries) == 1
        assert queries[0][1] == "Arsenal vs Chelsea"

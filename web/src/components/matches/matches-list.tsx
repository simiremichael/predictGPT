"use client";

import { useState, useEffect } from "react";
import { Calendar, Filter, X } from "lucide-react";
import { api } from "@/lib/api";
import { MatchCard } from "@/components/match-card";
import { LoadingState, EmptyState } from "@/components/loading-states";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Pagination } from "@/components/ui/pagination";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import type { MatchBrief } from "@/types/models";

const TOP_LEAGUES = [
  { id: "39", name: "Premier League" },
  { id: "140", name: "La Liga" },
  { id: "135", name: "Serie A" },
  { id: "78", name: "Bundesliga" },
  { id: "61", name: "Ligue 1" },
];

interface MatchesListProps {
  initialPage: number;
  initialPageSize: number;
  initialLeagueId: string;
  initialTeamId: string;
  initialStatus: string;
  initialDate: string;
  today: boolean;
  upcoming: boolean;
}

export function MatchesList({
  initialPage,
  initialPageSize,
  initialLeagueId,
  initialTeamId,
  initialStatus,
  initialDate,
  today,
  upcoming,
}: MatchesListProps) {
  const [page, setPage] = useState(initialPage);
  const [pageSize, setPageSize] = useState(initialPageSize);
  const [leagueId, setLeagueId] = useState(initialLeagueId);
  const [teamId, setTeamId] = useState(initialTeamId);
  const [status, setStatus] = useState(initialStatus);
  const [date, setDate] = useState(initialDate);
  const [result, setResult] = useState<{
    data: MatchBrief[];
    meta: {
      page: number;
      page_size: number;
      total: number;
      total_pages: number;
    };
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function fetchMatches(
    requestedPage = page,
    requestedPageSize = pageSize,
    filterOverrides: Partial<{
      leagueId: string;
      teamId: string;
      status: string;
      date: string;
    }> = {},
  ) {
    const requestedLeagueId = filterOverrides.leagueId ?? leagueId;
    const requestedTeamId = filterOverrides.teamId ?? teamId;
    const requestedStatus = filterOverrides.status ?? status;
    const requestedDate = filterOverrides.date ?? date;

    setLoading(true);
    setError(null);
    try {
      let data;
      if (today) {
        data = await api.getTodayMatches({
          league_id: requestedLeagueId || undefined,
          page: requestedPage,
          page_size: requestedPageSize,
        });
      } else if (upcoming) {
        data = await api.getUpcomingMatches({
          days: 7,
          league_id: requestedLeagueId || undefined,
          team_id: requestedTeamId || undefined,
          page: requestedPage,
          page_size: requestedPageSize,
        });
      } else {
        data = await api.listMatches({
          league_id: requestedLeagueId || undefined,
          team_id: requestedTeamId || undefined,
          status: requestedStatus || undefined,
          date: requestedDate || undefined,
          page: requestedPage,
          page_size: requestedPageSize,
        });
      }
      setResult(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load matches");
    } finally {
      setLoading(false);
    }
  }

  // Initial fetch
  useEffect(() => {
    fetchMatches();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handlePageChange = (newPage: number) => {
    setPage(newPage);
    void fetchMatches(newPage);
  };

  const handleFilterChange = (
    newPage: number = 1,
    filterOverrides: Partial<{
      leagueId: string;
      teamId: string;
      status: string;
      date: string;
    }> = {},
  ) => {
    setPage(newPage);
    void fetchMatches(newPage, pageSize, filterOverrides);
  };

  const clearFilters = () => {
    setLeagueId("");
    setTeamId("");
    setStatus("");
    setDate("");
    handleFilterChange(1, {
      leagueId: "",
      teamId: "",
      status: "",
      date: "",
    });
  };

  if (error) {
    return <EmptyState title="Unable to load matches" description={error} />;
  }

  if (loading && !result) {
    return <LoadingState message="Loading matches..." />;
  }

  if (!result || result.data.length === 0) {
    return (
      <EmptyState
        title="No matches found"
        description="Try adjusting your filters or check back later."
      />
    );
  }

  const hasFilters = leagueId || teamId || status || date;
  const topLeagueOrder = new Map(
    TOP_LEAGUES.flatMap((league, index) => [
      [league.id, index] as const,
      [league.name.toLocaleLowerCase(), index] as const,
    ]),
  );
  const groupedMatches = new Map<string, MatchBrief[]>();

  for (const match of result.data) {
    const key =
      match.league_id || match.league_name?.toLocaleLowerCase() || "other";
    groupedMatches.set(key, [...(groupedMatches.get(key) ?? []), match]);
  }

  const matchGroups = [...groupedMatches.entries()]
    .map(([key, matches]) => {
      const firstMatch = matches[0];
      const league = TOP_LEAGUES.find(
        (candidate) =>
          candidate.id === firstMatch.league_id ||
          candidate.name.toLocaleLowerCase() ===
            firstMatch.league_name?.toLocaleLowerCase(),
      );
      const label =
        firstMatch.league_name ||
        league?.name ||
        (key === "other" ? "Other matches" : `League ${key}`);
      const priority =
        topLeagueOrder.get(firstMatch.league_id || "") ??
        topLeagueOrder.get(firstMatch.league_name?.toLocaleLowerCase() || "") ??
        TOP_LEAGUES.length;

      return { key, label, matches, priority };
    })
    .sort(
      (first, second) =>
        first.priority - second.priority ||
        first.label.localeCompare(second.label),
    );

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="surface-card rounded-[1.5rem] p-4">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-wrap items-center gap-3">
            <Select
              value={pageSize.toString()}
              onValueChange={(value) => {
                const nextPageSize = Number(value);
                setPageSize(nextPageSize);
                setPage(1);
                void fetchMatches(1, nextPageSize);
              }}
            >
              <SelectTrigger className="w-[140px]">
                <SelectValue placeholder="Per page" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="10">10 per page</SelectItem>
                <SelectItem value="20">20 per page</SelectItem>
                <SelectItem value="50">50 per page</SelectItem>
              </SelectContent>
            </Select>

            <Input
              placeholder="League ID"
              value={leagueId}
              onChange={(e) => setLeagueId(e.target.value)}
              className="w-[180px]"
            />
            <Input
              placeholder="Team ID"
              value={teamId}
              onChange={(e) => setTeamId(e.target.value)}
              className="w-[180px]"
            />
            <Input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className="w-[180px]"
            />
            <Select value={status} onValueChange={(value) => setStatus(value)}>
              <SelectTrigger className="w-[160px]">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="">All</SelectItem>
                <SelectItem value="scheduled">Scheduled</SelectItem>
                <SelectItem value="live">Live</SelectItem>
                <SelectItem value="finished">Finished</SelectItem>
                <SelectItem value="postponed">Postponed</SelectItem>
                <SelectItem value="cancelled">Cancelled</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {hasFilters && (
            <Button
              variant="ghost"
              size="sm"
              onClick={clearFilters}
              className="flex items-center gap-1"
            >
              <X className="h-3 w-3" />
              Clear filters
            </Button>
          )}
        </div>
      </div>

      {/* Matches List */}
      <div className="space-y-6">
        {matchGroups.map((group) => (
          <section key={group.key} className="space-y-3">
            <h2 className="border-b border-border pb-2 text-sm font-bold text-foreground">
              {group.label}
              <span className="ml-2 font-normal text-muted-foreground">
                {group.matches.length}
              </span>
            </h2>
            {group.matches.map((match) => (
              <MatchCard
                key={match.id}
                match={match}
                showPrediction={false}
                variant="compact"
              />
            ))}
          </section>
        ))}
      </div>

      {/* Pagination */}
      <Pagination
        page={result.meta.page}
        pageSize={result.meta.page_size}
        total={result.meta.total}
        totalPages={result.meta.total_pages}
        onPageChange={handlePageChange}
        className="justify-center mt-6"
      />
    </div>
  );
}

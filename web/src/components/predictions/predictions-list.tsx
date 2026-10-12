"use client";

import { useState } from "react";
import { useInfiniteQuery } from "@tanstack/react-query";
import Link from "next/link";
import { Calendar } from "lucide-react";
import { api } from "@/lib/api";
import {
  LoadingState,
  EmptyState,
} from "@/components/loading-states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { AIGeneratedBadge } from "@/components/ai-generated-badge";
import type { PredictionHistoryItem } from "@/types/models";
import { getConfidenceColor } from "@/lib/predictions";

interface PredictionsListProps {
  pageSize: number;
  matchId?: string;
  leagueId?: string;
  teamId?: string;
}

export function PredictionsList({
  pageSize: initialPageSize,
  matchId,
  leagueId,
  teamId,
}: PredictionsListProps) {
  const [filterPlayed, setFilterPlayed] = useState<boolean | null>(null);
  const [filterDate, setFilterDate] = useState<string | null>(null);
  const todayStr = new Date().toISOString().split("T")[0];

  const {
    data: result,
    error,
    isPending: loading,
    hasNextPage,
    fetchNextPage,
    isFetchingNextPage,
  } = useInfiniteQuery({
    queryKey: [
      "predictions",
      matchId,
      leagueId,
      teamId,
      filterPlayed,
      filterDate,
      initialPageSize,
    ],
    initialPageParam: 1,
    queryFn: ({ pageParam }) =>
      api.getPredictions({
        match_id: matchId || undefined,
        league_id: leagueId || undefined,
        team_id: teamId || undefined,
        page: pageParam,
        page_size: initialPageSize,
        played: filterPlayed ?? undefined,
        kickoff_date: filterDate ?? undefined,
      }),
    getNextPageParam: (lastPage) =>
      lastPage.meta.page < lastPage.meta.total_pages
        ? lastPage.meta.page + 1
        : undefined,
  });

  const rows = result?.pages.flatMap((pageResult) => pageResult.data) ?? [];

  if (error && !result) {
    return (
      <EmptyState
        title="Failed to load predictions"
        description={error.message || "Please try again later."}
      />
    );
  }

  if (loading && !result) {
    return <LoadingState message="Loading predictions..." />;
  }

  if (!result || rows.length === 0) {
    return (
      <EmptyState
        title="No predictions found"
        description="Predictions will appear once generated for upcoming matches."
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <Button
          size="sm"
          variant={filterDate === todayStr ? "default" : "outline"}
          onClick={() => setFilterDate(todayStr)}
        >
          Today
        </Button>
        <fieldset className="flex items-center gap-3 rounded-md border border-border px-3 py-1.5 text-sm">
          <legend className="sr-only">Match status</legend>
          {([
            ["all", null, "All"],
            ["played", true, "Played"],
            ["unplayed", false, "Unplayed"],
          ] as const).map(([value, played, label]) => (
            <label key={value} className="flex cursor-pointer items-center gap-1.5">
              <input
                type="radio"
                name="prediction-played-filter"
                value={value}
                checked={filterPlayed === played}
                onChange={() => setFilterPlayed(played)}
                className="accent-primary"
              />
              {label}
            </label>
          ))}
        </fieldset>
        <div className="relative">
          <Calendar className="absolute left-2 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            type="date"
            value={filterDate ?? ""}
            onChange={(e) => setFilterDate(e.target.value || null)}
            className="rounded-md border border-border bg-background pl-8 pr-2 py-1 text-sm"
          />
        </div>
        {(filterPlayed !== null || filterDate) && (
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              setFilterPlayed(null);
              setFilterDate(null);
            }}
          >
            Clear
          </Button>
        )}
      </div>
      {rows.map((item: PredictionHistoryItem) => (
        <PredictionItem key={item.prediction_id} item={item} />
      ))}
      {error && <p className="text-center text-sm text-destructive">{error.message}</p>}
      {hasNextPage && (
        <div className="flex justify-center py-2">
          <Button
            variant="outline"
            onClick={() => void fetchNextPage()}
            disabled={isFetchingNextPage}
          >
            {isFetchingNextPage ? "Loading..." : "Load more"}
          </Button>
        </div>
      )}
    </div>
  );
}

function PredictionItem({ item }: { item: PredictionHistoryItem }) {
  const confidenceInfo = getConfidenceColor(item.model_confidence);

  const renderVerify = (
    checked: boolean | null | undefined,
  ) => {
    if (checked === true) {
      return (
        <span className="text-center text-green-600" aria-label="Passed">
          ✓
        </span>
      );
    }
    return (
      <span className="text-center text-red-600" aria-label="Failed">
        ✗
      </span>
    );
  };

  return (
    <Link href={`/predictions/${item.prediction_id}`}>
      <div className="group cursor-pointer rounded-[1.5rem] border border-border/80 bg-card/85 p-4 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-[0_18px_36px_rgba(15,23,42,0.08)]">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex min-w-0 flex-1 items-center gap-3">
            <div className="flex items-center gap-2">
              <Badge
                variant="secondary"
                className={confidenceInfo.bg}
                title="Heuristic model confidence based on data quality and how clearly the 1X2 probabilities favor one outcome. It is not a guarantee."
              >
                <span className={confidenceInfo.text}>
                  {confidenceInfo.label}
                </span>
              </Badge>
              <AIGeneratedBadge />
              <span className="text-[10px] font-bold uppercase tracking-[0.12em] text-muted-foreground">
                {item.model_version}
              </span>
            </div>

            <div className="min-w-0 font-semibold tracking-tight text-foreground">
              <span className="truncate">{item.match_home_team}</span>
              <span className="mx-2 text-muted-foreground">vs</span>
              <span className="truncate">{item.match_away_team}</span>
            </div>
          </div>

          <div className="flex items-center gap-3 text-right">
            {/* Win prediction */}
            <div className="rounded-xl bg-muted/40 px-3 py-1.5 text-center">
              <div className="text-[9px] uppercase tracking-[0.12em] text-muted-foreground">
                Win
              </div>
              <div className="mt-0.5 text-sm font-bold text-foreground">
                {item.home_probability != null &&
                item.home_probability >= (item.draw_probability ?? 0) &&
                item.home_probability >= (item.away_probability ?? 0)
                  ? "H"
                  : item.draw_probability != null &&
                      item.draw_probability >= (item.away_probability ?? 0)
                    ? "D"
                    : "A"}
              </div>
              <div className="text-[9px] text-muted-foreground">
                {renderVerify(item.admin_verify_win)}
              </div>
            </div>

            {/* Over 2.5 prediction */}
            <div className="rounded-xl bg-muted/40 px-3 py-1.5 text-center">
              <div className="text-[9px] uppercase tracking-[0.12em] text-muted-foreground">
                O 2.5
              </div>
              <div className="mt-0.5 text-sm font-bold text-foreground">
                {item.over_2_5_probability != null &&
                item.over_2_5_probability >= 0.5
                  ? "O2.5"
                  : "U2.5"}
              </div>
              <div className="text-[9px] text-muted-foreground">
                {renderVerify(item.admin_verify_over_2_5)}
              </div>
            </div>

            {/* BTTS prediction */}
            <div className="rounded-xl bg-muted/40 px-3 py-1.5 text-center">
              <div className="text-[9px] uppercase tracking-[0.12em] text-muted-foreground">
                BTTS
              </div>
              <div className="mt-0.5 text-sm font-bold text-foreground">
                {item.btts_probability != null &&
                item.btts_probability >= 0.5
                  ? "GG"
                  : "NG"}
              </div>
              <div className="text-[9px] text-muted-foreground">
                {renderVerify(item.admin_verify_gg)}
              </div>
            </div>

            <div className="text-right text-xs text-muted-foreground">
              <Calendar className="mr-1 inline h-3 w-3" />
              {item.match_kickoff
                ? new Date(item.match_kickoff).toLocaleDateString()
                : new Date(item.generated_at).toLocaleDateString()}
            </div>
          </div>

        </div>
      </div>
    </Link>
    );
  }


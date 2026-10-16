"use client";

import { useEffect, useState } from "react";
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
import type { PaginatedResult } from "@/lib/api";
import { getConfidenceColor } from "@/lib/predictions";
import { useAuth } from "@/contexts/auth";

const FREE_LIMIT = 2;

interface PredictionsListProps {
  pageSize: number;
  played: boolean;
  minElapsedMinutes?: number;
  maxElapsedMinutes?: number;
  newestFirst?: boolean;
  showDateFilter?: boolean;
  matchId?: string;
  leagueId?: string;
  teamId?: string;
  initialData?: PaginatedResult<PredictionHistoryItem>;
}

export function PredictionsList({
  pageSize: initialPageSize,
  played,
  minElapsedMinutes,
  maxElapsedMinutes,
  newestFirst = false,
  showDateFilter = true,
  matchId,
  leagueId,
  teamId,
  initialData,
}: PredictionsListProps) {
  const { user } = useAuth();
  const [filterDate, setFilterDate] = useState<string | null>(null);
  const [nowMs, setNowMs] = useState(() => Date.now());
  const todayStr = new Date().toISOString().split("T")[0];

  useEffect(() => {
    const timer = window.setInterval(() => setNowMs(Date.now()), 60_000);
    return () => window.clearInterval(timer);
  }, []);

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
      played,
      minElapsedMinutes,
      maxElapsedMinutes,
      newestFirst,
      filterDate,
      initialPageSize,
      user?.id,
    ],
    initialPageParam: 1,
    initialData: filterDate === null && !user && initialData
      ? {
          pages: [initialData],
          pageParams: [1],
        }
      : undefined,
    queryFn: ({ pageParam }) =>
      api.getPredictions({
        match_id: matchId || undefined,
        league_id: leagueId || undefined,
        team_id: teamId || undefined,
        page: pageParam,
        page_size: initialPageSize,
        played,
        min_elapsed_minutes: minElapsedMinutes,
        max_elapsed_minutes: maxElapsedMinutes,
        kickoff_date: filterDate ?? undefined,
        newest_first: newestFirst,
      }),
    refetchOnWindowFocus: false,
    getNextPageParam: (lastPage) =>
      lastPage.meta.page < lastPage.meta.total_pages
        ? lastPage.meta.page + 1
        : undefined,
  });

  const rows = result?.pages.flatMap((pageResult) => pageResult.data) ?? [];
  const firstPageMeta = result?.pages[0]?.meta;
  const isSubscribed = firstPageMeta?.is_subscribed ?? true;
  const freeRemaining = firstPageMeta?.free_predictions_remaining;

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
        description={
          played
            ? "Completed match results will appear here."
            : "Predictions for unfinished matches will appear here."
        }
      />
    );
  }

  return (
    <div className="space-y-4">
      {showDateFilter && <div className="flex flex-wrap items-center gap-3">
        <Button
          size="sm"
          variant={filterDate === todayStr ? "default" : "outline"}
          onClick={() => setFilterDate(todayStr)}
        >
          Today
        </Button>
        <div className="relative">
          <Calendar className="absolute left-2 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            type="date"
            value={filterDate ?? ""}
            onChange={(e) => setFilterDate(e.target.value || null)}
            className="rounded-md border border-border bg-background pl-8 pr-2 py-1 text-sm"
          />
        </div>
        {filterDate && (
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              setFilterDate(null);
            }}
          >
            Clear
          </Button>
        )}
       </div>}
      {(!isSubscribed || freeRemaining !== undefined) && (
        <div className="rounded-xl border border-primary/20 bg-primary/5 p-4 text-sm">
          <p className="font-semibold text-foreground">
            Showing first {FREE_LIMIT} predictions
          </p>
          <p className="text-muted-foreground">
            Subscribe for $5/month to see all predictions with full market details.
          </p>
          <Link
            href={user ? "/subscription" : "/signup"}
            className="mt-2 inline-block font-medium text-primary hover:underline"
          >
            {user ? "Go to subscription →" : "Create an account / subscribe →"}
          </Link>
        </div>
      )}
      {rows.map((item: PredictionHistoryItem) => (
        <PredictionItem key={item.prediction_id} item={item} played={played} nowMs={nowMs} />
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

function PredictionItem({
  item,
  played,
  nowMs,
}: {
  item: PredictionHistoryItem;
  played: boolean;
  nowMs: number;
}) {
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
              <MatchStateBadge kickoffAt={item.match_kickoff} played={played} nowMs={nowMs} />
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
            {played && item.home_score != null && item.away_score != null && (
              <div className="rounded-xl border border-primary/20 bg-primary/5 px-3 py-1.5 text-center">
                <div className="text-[9px] uppercase tracking-[0.12em] text-muted-foreground">
                  Full time
                </div>
                <div className="mt-0.5 text-sm font-bold text-foreground">
                  {item.home_score} - {item.away_score}
                </div>
              </div>
            )}
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
              {played && (
                <div className="text-[9px] text-muted-foreground">
                  {renderVerify(item.admin_verify_win)}
                </div>
              )}
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
              {played && (
                <div className="text-[9px] text-muted-foreground">
                  {renderVerify(item.admin_verify_over_2_5)}
                </div>
              )}
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
              {played && (
                <div className="text-[9px] text-muted-foreground">
                  {renderVerify(item.admin_verify_gg)}
                </div>
              )}
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

function MatchStateBadge({
  kickoffAt,
  played,
  nowMs,
}: {
  kickoffAt?: string | null;
  played: boolean;
  nowMs: number;
}) {
  const kickoffMs = kickoffAt ? new Date(kickoffAt).getTime() : Number.NaN;
  const elapsedMinutes = Number.isFinite(kickoffMs)
    ? (nowMs - kickoffMs) / 60_000
    : null;
  const isInPlay =
    !played &&
    elapsedMinutes !== null &&
    elapsedMinutes >= 0 &&
    elapsedMinutes <= 100;
  const label = played ? "Played" : isInPlay ? "In-play" : "Upcoming";

  return (
    <Badge
      variant="outline"
      className={
        isInPlay && !played
          ? "border-amber-500/40 bg-amber-500/10 text-amber-700"
          : "border-border bg-background/70 text-muted-foreground"
      }
    >
      {label}
    </Badge>
  );
}


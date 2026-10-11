"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { TrendingUp, Calendar } from "lucide-react";
import { api } from "@/lib/api";
import {
  LoadingState,
  EmptyState,
  PaginationControls,
} from "@/components/loading-states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { PredictionHistoryItem } from "@/types/models";
import { getConfidenceColor } from "@/lib/predictions";

interface PredictionsListProps {
  page: number;
  pageSize: number;
  matchId?: string;
  leagueId?: string;
  teamId?: string;
}

export function PredictionsList({
  page: initialPage,
  pageSize: initialPageSize,
  matchId,
  leagueId,
  teamId,
}: PredictionsListProps) {
  const [page, setPage] = useState(initialPage);
  const [result, setResult] = useState<{
    data: PredictionHistoryItem[];
    meta: { total_pages?: number; total?: number };
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterPlayed, setFilterPlayed] = useState<boolean | null>(null);
  const [filterDate, setFilterDate] = useState<string | null>(null);
  const todayStr = new Date().toISOString().split("T")[0];

  async function fetchPredictions(requestedPage: number = page) {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getPredictions({
        match_id: matchId || undefined,
        league_id: leagueId || undefined,
        team_id: teamId || undefined,
        page: requestedPage,
        page_size: initialPageSize,
        played: filterPlayed ?? undefined,
        kickoff_date: filterDate ?? undefined,
      });
      setResult(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load predictions");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void fetchPredictions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filterPlayed, filterDate]);

  const handlePageChange = (newPage: number) => {
    setPage(newPage);
    const url = new URL(window.location.href);
    url.searchParams.set("page", String(newPage));
    window.history.pushState({}, "", url.toString());
    void fetchPredictions(newPage);
  };

  if (error) {
    return (
      <EmptyState
        title="Failed to load predictions"
        description="Please try again later."
      />
    );
  }

  if (loading && !result) {
    return <LoadingState message="Loading predictions..." />;
  }

  if (!result || result.data.length === 0) {
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
        <Button
          size="sm"
          variant={filterPlayed === true ? "default" : "outline"}
          onClick={() => setFilterPlayed(true)}
        >
          Played
        </Button>
        <Button
          size="sm"
          variant={filterPlayed === false ? "default" : "outline"}
          onClick={() => setFilterPlayed(false)}
        >
          Not played
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
      {result.data.map((item: PredictionHistoryItem) => (
        <PredictionItem key={item.prediction_id} item={item} />
      ))}
      <PaginationControls
        currentPage={page}
        totalPages={result.meta.total_pages || 1}
        onPageChange={handlePageChange}
      />
    </div>
  );
}

function PredictionItem({ item }: { item: PredictionHistoryItem }) {
  const confidenceInfo = getConfidenceColor(item.model_confidence);

  const matchPassed =
    item.match_kickoff &&
    new Date(item.match_kickoff).getTime() + 100 * 60 * 1000 < Date.now();

  const renderVerify = (
    checked: boolean | null | undefined,
  ) => {
    if (checked === true) {
      return <span className="text-center text-green-600">✓</span>;
    }
    if (matchPassed) {
      return <span className="text-center text-red-600">✗</span>;
    }
    if (checked === false) {
      return <span className="text-center text-red-600">✗</span>;
    }
    return null;
  };

  return (
    <Link href={`/predictions/${item.prediction_id}`}>
      <div className="group cursor-pointer rounded-[1.5rem] border border-border/80 bg-card/85 p-4 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-[0_18px_36px_rgba(15,23,42,0.08)]">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex min-w-0 flex-1 items-center gap-3">
            <div className="flex items-center gap-2">
              <Badge variant="secondary" className={confidenceInfo.bg}>
                <span className={confidenceInfo.text}>
                  {confidenceInfo.label}
                </span>
              </Badge>
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

          {item.ai_adjustment_applied && (
            <div className="mt-3 inline-flex items-center gap-1 rounded-full border border-emerald-500/20 bg-emerald-500/5 px-2.5 py-1 text-[11px] font-semibold text-emerald-600">
              <TrendingUp className="h-3 w-3" />
              AI-adjusted
            </div>
          )}

          {matchPassed && (
            <div className="mt-3 flex items-center gap-3 text-[10px]">
              <span>Verified:</span>
              <span title="BTTS">{renderVerify(item.admin_verify_gg)}</span>
              <span title="Win">{renderVerify(item.admin_verify_win)}</span>
              <span title="Over 2.5">{renderVerify(item.admin_verify_over_2_5)}</span>
            </div>
          )}
          {item.admin_verify_gg !== null &&
            item.admin_verify_gg !== undefined &&
            item.admin_verify_win !== null &&
            item.admin_verify_win !== undefined &&
            item.admin_verify_over_2_5 !== null &&
            item.admin_verify_over_2_5 !== undefined &&
            !matchPassed && (
              <div className="mt-3 flex items-center gap-3 text-[10px]">
                <span>Verified:</span>
                <span title="BTTS">{renderVerify(item.admin_verify_gg)}</span>
                <span title="Win">{renderVerify(item.admin_verify_win)}</span>
                <span title="Over 2.5">{renderVerify(item.admin_verify_over_2_5)}</span>
              </div>
            )}
        </div>
      </div>
    </Link>
    );
  }


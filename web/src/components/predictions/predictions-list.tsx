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
  }, []);

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

          <div className="flex items-center gap-4 text-right">
            <div className="grid grid-cols-3 gap-2 text-center">
              <div className="rounded-xl bg-muted/40 px-2 py-1.5">
                <div className="text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
                  H
                </div>
                <div className="mt-1 text-sm font-bold text-foreground">
                  {item.home_probability
                    ? `${Math.round(item.home_probability * 100)}%`
                    : "N/A"}
                </div>
              </div>
              <div className="rounded-xl bg-muted/40 px-2 py-1.5">
                <div className="text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
                  D
                </div>
                <div className="mt-1 text-sm font-bold text-foreground">
                  {item.draw_probability
                    ? `${Math.round(item.draw_probability * 100)}%`
                    : "N/A"}
                </div>
              </div>
              <div className="rounded-xl bg-muted/40 px-2 py-1.5">
                <div className="text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
                  A
                </div>
                <div className="mt-1 text-sm font-bold text-foreground">
                  {item.away_probability
                    ? `${Math.round(item.away_probability * 100)}%`
                    : "N/A"}
                </div>
              </div>
            </div>

            <div className="text-right text-xs text-muted-foreground">
              <Calendar className="mr-1 inline h-3 w-3" />
              {new Date(item.generated_at).toLocaleDateString()}
            </div>
          </div>
        </div>

        {item.ai_adjustment_applied && (
          <div className="mt-3 inline-flex items-center gap-1 rounded-full border border-emerald-500/20 bg-emerald-500/5 px-2.5 py-1 text-[11px] font-semibold text-emerald-600">
            <TrendingUp className="h-3 w-3" />
            AI-adjusted
          </div>
        )}
      </div>
    </Link>
  );
}

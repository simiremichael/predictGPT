"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { LoadingState, EmptyState } from "@/components/loading-states";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Pagination } from "@/components/ui/pagination";
import type { League } from "@/types/models";
import Link from "next/link";
import { Trophy } from "lucide-react";

interface LeaguesListProps {
  initialPage: number;
  initialPageSize: number;
  initialCountry: string;
  initialIsActive: boolean;
}

export function LeaguesList({
  initialPage,
  initialPageSize,
  initialCountry,
  initialIsActive,
}: LeaguesListProps) {
  const [page, setPage] = useState(initialPage);
  const [pageSize, setPageSize] = useState(initialPageSize);
  const [country, setCountry] = useState(initialCountry);
  const [isActive, setIsActive] = useState(initialIsActive);
  const [result, setResult] = useState<{
    data: League[];
    meta: { page: number; page_size: number; total: number; total_pages: number };
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  async function fetchLeagues() {
    setLoading(true);
    setError(false);
    try {
      const data = await api.listLeagues({
        page,
        page_size: pageSize,
        country: country || undefined,
        is_active: isActive,
      });
      setResult(data);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }

  // Initial fetch and refetch when filters change
  useEffect(() => {
    fetchLeagues();
  }, [page, pageSize, country, isActive]); // eslint-disable-line react-hooks/exhaustive-deps

  if (error) {
    return <LoadingState message="Failed to load leagues. Please try again." />;
  }

  if (loading && !result) {
    return <LoadingState message="Loading leagues..." />;
  }

  if (!result || result.data.length === 0) {
    return (
      <EmptyState
        title="No leagues found"
        description="No football leagues are currently available."
      />
    );
  }

  const countries = Array.from(new Set(result.data.map((l) => l.country).filter(Boolean))) as string[];

  return (
    <div className="space-y-6">
      <section className="surface-card rounded-[1.75rem] p-5 sm:p-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="section-kicker mb-2">Directory</p>
            <h1 className="text-3xl font-black tracking-[-0.06em] text-foreground">
              Leagues
            </h1>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2">
              <Select
                value={country}
                onValueChange={(value) => {
                  setCountry(value);
                  setPage(1);
                }}
              >
                <SelectTrigger className="w-[180px]">
                  <SelectValue placeholder="All Countries" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="">All Countries</SelectItem>
                  {countries.map((c) => (
                    <SelectItem key={c} value={c}>
                      {c}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select
                value={isActive ? "true" : "false"}
                onValueChange={(value) => {
                  setIsActive(value === "true");
                  setPage(1);
                }}
              >
                <SelectTrigger className="w-[140px]">
                  <SelectValue placeholder="Status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="true">Active</SelectItem>
                  <SelectItem value="false">Inactive</SelectItem>
                </SelectContent>
              </Select>
              <Select
                value={pageSize.toString()}
                onValueChange={(value) => {
                  setPageSize(parseInt(value, 10));
                  setPage(1);
                }}
              >
                <SelectTrigger className="w-[140px]">
                  <SelectValue placeholder="Per page" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="10">10 per page</SelectItem>
                  <SelectItem value="20">20 per page</SelectItem>
                  <SelectItem value="50">50 per page</SelectItem>
                  <SelectItem value="100">100 per page</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <Badge
              variant="outline"
              className="w-fit rounded-full border-primary/20 bg-primary/5 px-3 py-1.5 text-xs font-semibold text-primary"
            >
              {result.meta.total} leagues
            </Badge>
          </div>
        </div>
      </section>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {result.data.map((league: League) => (
          <Link
            key={league.id}
            href={`/leagues/${league.id}`}
            className="group block"
          >
            <div className="surface-card flex h-full flex-col rounded-[1.5rem] p-4 transition-all duration-200 hover:-translate-y-1 hover:shadow-[0_20px_44px_rgba(15,23,42,0.08)]">
              <div className="flex items-center gap-3">
                <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-gradient-to-br from-primary/12 to-cyan-500/10 text-primary ring-1 ring-primary/10">
                  <Trophy className="h-5 w-5" />
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="truncate font-bold tracking-tight text-foreground transition-colors group-hover:text-primary">
                    {league.name}
                  </h3>
                  {league.country && (
                    <p className="truncate text-sm text-muted-foreground">
                      {league.country}
                    </p>
                  )}
                </div>
              </div>
              <div className="mt-4 border-t border-border/80 pt-3">
                <Badge
                  variant={league.is_active ? "default" : "secondary"}
                  className="text-xs font-semibold"
                >
                  {league.is_active ? "Active" : "Inactive"}
                </Badge>
              </div>
            </div>
          </Link>
        ))}
      </div>

      <Pagination
        page={result.meta.page}
        pageSize={result.meta.page_size}
        total={result.meta.total}
        totalPages={result.meta.total_pages}
        onPageChange={setPage}
        className="justify-center mt-6"
      />
    </div>
  );
}
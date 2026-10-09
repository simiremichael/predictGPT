"use client";

import { useState } from "react";
import { CheckSquare, RefreshCw, Search, Square, Trash2 } from "lucide-react";
import { useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, ApiError, type AdminLeague, type AdminTeam } from "@/lib/api";
import type {
  PredictionHistoryItem,
  MatchBrief,
  Scoreline,
} from "@/types/models";
import { LoadingState, EmptyState } from "@/components/loading-states";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Pagination } from "@/components/ui/pagination";

const PAGE_SIZE = 25;

function errMsg(e: unknown): string {
  if (e instanceof ApiError) return e.message;
  if (e instanceof Error) return e.message;
  return "An unexpected error occurred";
}

function metaMsg(meta: unknown, fallback: string): string {
  if (meta && typeof meta === "object" && "message" in meta) {
    const m = (meta as { message?: unknown }).message;
    return typeof m === "string" ? m : fallback;
  }
  return fallback;
}

function pct(v: number | null | undefined): string {
  return v == null ? "—" : `${Math.round(v * 100)}%`;
}

function Toggle({
  checked,
  onChange,
}: {
  checked: boolean;
  onChange: (next: boolean) => void;
}) {
  return (
    <button
      type="button"
      role="checkbox"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className="inline-flex h-4 w-4 items-center justify-center rounded-sm border border-border text-xs"
    >
      {checked ? (
        <CheckSquare className="h-3 w-3" />
      ) : (
        <Square className="h-3 w-3" />
      )}
    </button>
  );
}

/* ── Leagues ────────────────────────────────────────────── */
function AdminLeagues() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [searchTerm, setSearchTerm] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [actionId, setActionId] = useState<string | null>(null);

  const {
    data: listResult,
    error,
    isPending: loading,
  } = useQuery({
    queryKey: ["admin-leagues", page, searchTerm],
    queryFn: () =>
      api.admin.listLeagues({
        page,
        page_size: PAGE_SIZE,
        search: searchTerm || undefined,
      }),
  });

  const rows = listResult?.data ?? [];
  const total = listResult?.meta.total ?? 0;
  const totalPages = listResult?.meta.total_pages ?? 1;
  const allSelected = rows.length > 0 && rows.every((l) => selected.has(l.id));

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.admin.deleteLeague(id),
    onSuccess: (r) => {
      toast.success(metaMsg(r.meta, "League deleted"));
      queryClient.invalidateQueries({ queryKey: ["admin-leagues"] });
    },
    onError: (e) => toast.error(errMsg(e)),
  });
  const resyncMutation = useMutation({
    mutationFn: (id: string) => api.admin.resyncLeague(id),
    onSuccess: (r) => toast.success(metaMsg(r.meta, "Resynced")),
    onError: (e) => toast.error(errMsg(e)),
  });
  const bulkDeleteMutation = useMutation({
    mutationFn: (ids: string[]) => api.admin.deleteLeagues(ids),
    onSuccess: (r) => {
      toast.success(`Deleted ${r.data.deleted} league(s)`);
      queryClient.invalidateQueries({ queryKey: ["admin-leagues"] });
      setSelected(new Set());
    },
    onError: (e) => toast.error(errMsg(e)),
  });
  const fetchLeaguesMutation = useMutation({
    mutationFn: () => api.admin.fetchLeagues(),
    onSuccess: (r) => {
      toast.success(metaMsg(r.meta, "Leagues fetched"));
      queryClient.invalidateQueries({ queryKey: ["admin-leagues"] });
    },
    onError: (e) => toast.error(errMsg(e)),
  });

  async function remove(id: string) {
    if (!confirm(`Delete league ${id} and all scoped data?`)) return;
    setActionId(id);
    try {
      await deleteMutation.mutateAsync(id);
      setSelected((s) => {
        const copy = new Set(s);
        copy.delete(id);
        return copy;
      });
    } finally {
      setActionId(null);
    }
  }

  async function resync(id: string) {
    setActionId(id);
    try {
      await resyncMutation.mutateAsync(id);
    } finally {
      setActionId(null);
    }
  }

  async function bulkDelete() {
    const ids = Array.from(selected);
    if (!ids.length || !confirm(`Delete ${ids.length} leagues?`)) return;
    await bulkDeleteMutation.mutateAsync(ids);
    setSelected(new Set());
  }

  if (error)
    return (
      <EmptyState title="Failed to load leagues" description={errMsg(error)} />
    );
  if (loading && !listResult)
    return <LoadingState message="Loading leagues..." />;
  if (!listResult || rows.length === 0) {
    return (
      <EmptyState
        title={searchTerm ? "No leagues match your search" : "No leagues found"}
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            className="pl-9"
            placeholder="Search leagues..."
            value={searchTerm}
            onChange={(e) => {
              setSearchTerm(e.target.value);
              setPage(1);
              setSelected(new Set());
            }}
          />
        </div>
        <Button
          variant="outline"
          onClick={() => void fetchLeaguesMutation.mutate()}
          disabled={fetchLeaguesMutation.isPending}
        >
          {fetchLeaguesMutation.isPending ? "Fetching..." : "Fetch leagues"}
        </Button>
        <Button
          variant="outline"
          onClick={() => void bulkDelete()}
          disabled={selected.size === 0 || bulkDeleteMutation.isPending}
        >
          {bulkDeleteMutation.isPending
            ? "Deleting..."
            : `Delete (${selected.size})`}
        </Button>
      </div>

      <div className="overflow-x-auto rounded-xl border border-border/80">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="bg-muted/40">
              <th className="p-3">
                <Toggle
                  checked={allSelected}
                  onChange={(c) =>
                    setSelected(c ? new Set(rows.map((l) => l.id)) : new Set())
                  }
                />
              </th>
              <th className="px-3 py-2 font-medium">ID</th>
              <th className="px-3 py-2 font-medium">Provider ID</th>
              <th className="px-3 py-2 font-medium">Name</th>
              <th className="px-3 py-2 font-medium">Country</th>
              <th className="px-3 py-2 font-medium">Active</th>
              <th className="px-3 py-2 font-medium text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((l: AdminLeague) => (
              <tr key={l.id} className="border-t border-border/60">
                <td className="p-3">
                  <Toggle
                    checked={selected.has(l.id)}
                    onChange={(c) =>
                      setSelected((s) => {
                        const copy = new Set(s);
                        if (c) {
                          copy.add(l.id);
                        } else {
                          copy.delete(l.id);
                        }
                        return copy;
                      })
                    }
                  />
                </td>
                <td className="px-3 py-2 font-mono text-xs">{l.id}</td>
                <td className="px-3 py-2 font-mono text-xs">
                  {l.provider_league_id ?? "—"}
                </td>
                <td className="px-3 py-2">{l.name}</td>
                <td className="px-3 py-2">{l.country ?? "—"}</td>
                <td className="px-3 py-2">{l.is_active ? "Yes" : "No"}</td>
                <td className="px-3 py-2 text-right">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => void resync(l.id)}
                    disabled={actionId === l.id}
                  >
                    {actionId === l.id ? (
                      "..."
                    ) : (
                      <RefreshCw className="h-3 w-3" />
                    )}
                  </Button>
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={() => void remove(l.id)}
                    disabled={actionId === l.id}
                  >
                    <Trash2 className="h-3 w-3" />
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {rows.length > 0 && totalPages > 1 && (
        <Pagination
          page={page}
          pageSize={PAGE_SIZE}
          total={total}
          totalPages={totalPages}
          onPageChange={setPage}
          className="justify-center"
        />
      )}
    </div>
  );
}

/* ── Teams ─────────────────────────────────────────────── */
function AdminTeams() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [searchTerm, setSearchTerm] = useState("");
  const [leagueId, setLeagueId] = useState("");
  const [fetchLeagueId, setFetchLeagueId] = useState("");
  const [fetchSeasonId, setFetchSeasonId] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [actionId, setActionId] = useState<string | null>(null);

  const {
    data: listResult,
    error,
    isPending: loading,
  } = useQuery({
    queryKey: ["admin-teams", page, searchTerm, leagueId],
    queryFn: () =>
      api.admin.listTeams({
        page,
        page_size: PAGE_SIZE,
        search: searchTerm || undefined,
        league_id: leagueId || undefined,
      }),
  });

  const rows = listResult?.data ?? [];
  const total = listResult?.meta.total ?? 0;
  const totalPages = listResult?.meta.total_pages ?? 1;
  const allSelected = rows.length > 0 && rows.every((t) => selected.has(t.id));

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.admin.deleteTeam(id),
    onSuccess: (r) => {
      toast.success(metaMsg(r.meta, "Team deleted"));
      queryClient.invalidateQueries({ queryKey: ["admin-teams"] });
    },
    onError: (e) => toast.error(errMsg(e)),
  });
  const resyncMutation = useMutation({
    mutationFn: (id: string) => api.admin.resyncTeam(id),
    onSuccess: (r) => toast.success(metaMsg(r.meta, "Resynced")),
    onError: (e) => toast.error(errMsg(e)),
  });
  const bulkDeleteMutation = useMutation({
    mutationFn: (ids: string[]) => api.admin.deleteTeams(ids),
    onSuccess: (r) => {
      toast.success(`Deleted ${r.data.deleted} team(s)`);
      queryClient.invalidateQueries({ queryKey: ["admin-teams"] });
      setSelected(new Set());
    },
    onError: (e) => toast.error(errMsg(e)),
  });
  const fetchTeamsMutation = useMutation({
    mutationFn: (params: { league_id: string; season_id: string }) =>
      api.admin.fetchTeams(params),
    onSuccess: (r) => {
      toast.success(metaMsg(r.meta, "Teams fetched"));
      queryClient.invalidateQueries({ queryKey: ["admin-teams"] });
    },
    onError: (e) => toast.error(errMsg(e)),
  });

  async function remove(id: string) {
    if (!confirm(`Delete team ${id}?`)) return;
    setActionId(id);
    try {
      await deleteMutation.mutateAsync(id);
      setSelected((s) => {
        const copy = new Set(s);
        copy.delete(id);
        return copy;
      });
    } finally {
      setActionId(null);
    }
  }

  async function resync(id: string) {
    setActionId(id);
    try {
      await resyncMutation.mutateAsync(id);
    } finally {
      setActionId(null);
    }
  }

  async function bulkDelete() {
    const ids = Array.from(selected);
    if (!ids.length || !confirm(`Delete ${ids.length} teams?`)) return;
    await bulkDeleteMutation.mutateAsync(ids);
    setSelected(new Set());
  }

  if (error)
    return (
      <EmptyState title="Failed to load teams" description={errMsg(error)} />
    );
  if (loading && !listResult)
    return <LoadingState message="Loading teams..." />;
  if (!listResult || rows.length === 0) {
    return <EmptyState title="No teams found" />;
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            className="pl-9"
            placeholder="Search teams..."
            value={searchTerm}
            onChange={(e) => {
              setSearchTerm(e.target.value);
              setPage(1);
              setSelected(new Set());
            }}
          />
        </div>
        <Input
          className="w-44"
          placeholder="Provider league id (e.g. 85)"
          value={leagueId}
          onChange={(e) => {
            setLeagueId(e.target.value);
            setPage(1);
          }}
        />
        <Button
          variant="outline"
          onClick={() => void bulkDelete()}
          disabled={selected.size === 0 || bulkDeleteMutation.isPending}
        >
          {bulkDeleteMutation.isPending
            ? "Deleting..."
            : `Delete (${selected.size})`}
        </Button>
      </div>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
        <div className="flex-1">
          <label className="mb-1 block text-sm font-medium">
            Provider league id
          </label>
          <Input
            placeholder="e.g. 85"
            value={fetchLeagueId}
            onChange={(e) => setFetchLeagueId(e.target.value)}
          />
        </div>
        <div className="flex-1">
          <label className="mb-1 block text-sm font-medium">
            Provider season id
          </label>
          <Input
            placeholder="e.g. 2024.0"
            value={fetchSeasonId}
            onChange={(e) => setFetchSeasonId(e.target.value)}
          />
        </div>
        <Button
          onClick={() =>
            void fetchTeamsMutation.mutate({
              league_id: fetchLeagueId,
              season_id: fetchSeasonId,
            })
          }
          disabled={
            fetchTeamsMutation.isPending || !fetchLeagueId || !fetchSeasonId
          }
        >
          {fetchTeamsMutation.isPending ? "Fetching..." : "Fetch teams"}
        </Button>
      </div>

      <div className="overflow-x-auto rounded-xl border border-border/80">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="bg-muted/40">
              <th className="p-3">
                <Toggle
                  checked={allSelected}
                  onChange={(c) =>
                    setSelected(c ? new Set(rows.map((t) => t.id)) : new Set())
                  }
                />
              </th>
              <th className="px-3 py-2 font-medium">ID</th>
              <th className="px-3 py-2 font-medium">Provider ID</th>
              <th className="px-3 py-2 font-medium">League ID</th>
              <th className="px-3 py-2 font-medium">Name</th>
              <th className="px-3 py-2 font-medium">Matches</th>
              <th className="px-3 py-2 font-medium text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((t: AdminTeam) => (
              <tr key={t.id} className="border-t border-border/60">
                <td className="p-3">
                  <Toggle
                    checked={selected.has(t.id)}
                    onChange={(c) =>
                      setSelected((s) => {
                        const copy = new Set(s);
                        if (c) {
                          copy.add(t.id);
                        } else {
                          copy.delete(t.id);
                        }
                        return copy;
                      })
                    }
                  />
                </td>
                <td className="px-3 py-2 font-mono text-xs">{t.id}</td>
                <td className="px-3 py-2 font-mono text-xs">
                  {t.provider_team_id ?? "—"}
                </td>
                <td className="px-3 py-2 font-mono text-xs">
                  {t.league_id ?? "—"}
                </td>
                <td className="px-3 py-2">{t.name}</td>
                <td className="px-3 py-2">{t.match_count}</td>
                <td className="px-3 py-2 text-right">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => void resync(t.id)}
                    disabled={actionId === t.id}
                  >
                    {actionId === t.id ? (
                      "..."
                    ) : (
                      <RefreshCw className="h-3 w-3" />
                    )}
                  </Button>
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={() => void remove(t.id)}
                    disabled={actionId === t.id}
                  >
                    <Trash2 className="h-3 w-3" />
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {rows.length > 0 && totalPages > 1 && (
        <Pagination
          page={page}
          pageSize={PAGE_SIZE}
          total={total}
          totalPages={totalPages}
          onPageChange={setPage}
          className="justify-center"
        />
      )}
    </div>
  );
}

/* ── Fixtures (list + resync) ─────────────────────────────── */
const now = () => new Date().toISOString().slice(0, 10);

function FixturesTab() {
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState(() => now());
  const [leagueId, setLeagueId] = useState("");
  const [resyncResult, setResyncResult] = useState<string | null>(null);
  const [matchPage, setMatchPage] = useState(1);

  const resync = useMutation({
    mutationFn: () =>
      api.admin.resyncFixtures({
        date_from: dateFrom || undefined,
        date_to: dateTo,
        league_id: leagueId || undefined,
      }),
    onSuccess: (r) => {
      toast.success(metaMsg(r.meta, "Resynced fixtures"));
      setResyncResult(JSON.stringify(r.data));
    },
    onError: (e) => {
      toast.error(errMsg(e));
      setResyncResult(null);
    },
  });

  const {
    data: matchResult,
    error: matchError,
    isPending: matchLoading,
    refetch: refetchMatches,
  } = useQuery({
    queryKey: ["admin-fixtures", matchPage, dateFrom, dateTo, leagueId],
    queryFn: () =>
      api.listMatches({
        date_from: dateFrom || undefined,
        date_to: dateTo,
        league_id: leagueId || undefined,
        page: matchPage,
        page_size: PAGE_SIZE,
      }),
    staleTime: 60_000,
  });

  const matchRows = matchResult?.data ?? [];
  const matchTotal = matchResult?.meta.total ?? 0;
  const matchPages = matchResult?.meta.total_pages ?? 1;
  const fmtDate = (iso?: string | null) =>
    iso ? new Date(iso).toLocaleString() : "—";

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <label className="mb-1 block text-sm font-medium">
            Date from (optional)
          </label>
          <Input
            type="date"
            value={dateFrom}
            onChange={(e) => {
              setDateFrom(e.target.value);
              setMatchPage(1);
            }}
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium">
            Date to (required)
          </label>
          <Input
            type="date"
            value={dateTo}
            onChange={(e) => {
              setDateTo(e.target.value);
              setMatchPage(1);
            }}
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium">
            League ID (optional provider id)
          </label>
          <Input
            placeholder="e.g. 85"
            value={leagueId}
            onChange={(e) => {
              setLeagueId(e.target.value);
              setMatchPage(1);
            }}
          />
        </div>
        <div className="flex items-end gap-2">
          <Button
            onClick={() => void refetchMatches()}
            variant="outline"
            disabled={matchLoading}
            className="w-full"
          >
            <RefreshCw className="h-4 w-4" />
          </Button>
          <Button
            onClick={() => resync.mutate()}
            disabled={resync.isPending || !dateTo}
            className="w-full"
          >
            {resync.isPending ? "Resyncing..." : "Resync fixtures"}
          </Button>
        </div>
      </div>

      {resyncResult && (
        <pre className="overflow-x-auto rounded-xl border border-border/80 bg-muted/40 p-3 text-xs">
          {resyncResult}
        </pre>
      )}

      <div className="rounded-xl border border-border/80">
        <div className="flex items-center justify-between px-3 py-2 text-sm">
          <span className="text-muted-foreground">{matchTotal} fixtures</span>
          <span className="text-xs text-muted-foreground">
            {matchPages > 1 ? `Page ${matchPage} / ${matchPages}` : ""}
          </span>
        </div>
        {matchLoading && !matchResult ? (
          <LoadingState message="Loading fixtures..." />
        ) : matchError ? (
          <EmptyState
            title="Failed to load fixtures"
            description={errMsg(matchError)}
          />
        ) : matchRows.length === 0 ? (
          <EmptyState title="No fixtures found" />
        ) : (
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="bg-muted/40">
                <th className="px-3 py-2 font-medium">ID</th>
                <th className="px-3 py-2 font-medium">League</th>
                <th className="px-3 py-2 font-medium">Home</th>
                <th className="px-3 py-2 font-medium">Away</th>
                <th className="px-3 py-2 font-medium">Kickoff</th>
                <th className="px-3 py-2 font-medium">Status</th>
                <th className="px-3 py-2 font-medium">Score</th>
              </tr>
            </thead>
            <tbody>
              {matchRows.map((m: MatchBrief) => (
                <tr key={m.id} className="border-t border-border/60">
                  <td className="px-3 py-2 font-mono text-xs">{m.id}</td>
                  <td className="px-3 py-2">{m.league_name ?? "—"}</td>
                  <td className="px-3 py-2">{m.home_team_name ?? "—"}</td>
                  <td className="px-3 py-2">{m.away_team_name ?? "—"}</td>
                  <td className="px-3 py-2">{fmtDate(m.kickoff_at)}</td>
                  <td className="px-3 py-2">{m.status}</td>
                  <td className="px-3 py-2">
                    {m.home_score != null && m.away_score != null
                      ? `${m.home_score} - ${m.away_score}`
                      : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {matchPages > 1 && (
          <div className="p-2">
            <Pagination
              page={matchPage}
              pageSize={PAGE_SIZE}
              total={matchTotal}
              totalPages={matchPages}
              onPageChange={setMatchPage}
              className="justify-center"
            />
          </div>
        )}
      </div>
    </div>
  );
}

/* ── Predictions ───────────────────────────────────────── */
function AdminPredictions() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [actionId, setActionId] = useState<string | null>(null);
  const [forceRefresh, setForceRefresh] = useState(false);
  const [clearAll, setClearAll] = useState(false);
  const [currentJobId, setCurrentJobId] = useState<string | null>(null);

  const {
    data: listResult,
    error,
    isPending: loading,
  } = useQuery({
    queryKey: ["admin-predictions", page],
    queryFn: () =>
      api.admin.listPredictions({
        page,
        page_size: PAGE_SIZE,
        upcoming_only: false,
      }),
  });

  const rows = listResult?.data ?? [];
  const total = listResult?.meta.total ?? 0;
  const totalPages = listResult?.meta.total_pages ?? 1;
  const allSelected =
    rows.length > 0 && rows.every((p) => selected.has(p.prediction_id));

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.admin.deletePrediction(id),
    onSuccess: (r) => {
      toast.success(metaMsg(r.meta, "Prediction deleted"));
      queryClient.invalidateQueries({ queryKey: ["admin-predictions"] });
    },
    onError: (e) => toast.error(errMsg(e)),
  });
  const generateMutation = useMutation({
    mutationFn: (params?: {
      clear_all?: boolean;
      include_research?: boolean;
      force_refresh?: boolean;
      league_ids?: string[];
      limit?: number;
    }) =>
      api.admin.generatePredictions({
        clear_all: params?.clear_all,
        include_research: params?.include_research,
        force_refresh: params?.force_refresh,
        league_ids: params?.league_ids,
        limit: params?.limit,
      }),
    onSuccess: (r) => {
      const jobId = r.data.job_id;
      setCurrentJobId(jobId);
      toast.success(`Prediction generation started (job ${jobId})`);
      queryClient.invalidateQueries({ queryKey: ["admin-predictions"] });
    },
    onError: (e) => toast.error(errMsg(e)),
  });
  const bulkDeleteMutation = useMutation({
    mutationFn: (ids: string[]) => api.admin.deletePredictions(ids),
    onSuccess: (r) => {
      toast.success(`Deleted ${r.data.deleted} prediction(s)`);
      queryClient.invalidateQueries({ queryKey: ["admin-predictions"] });
      setSelected(new Set());
    },
    onError: (e) => toast.error(errMsg(e)),
  });

  const { data: jobStatus, isError: jobStatusError } = useQuery({
    queryKey: ["admin-job-status", currentJobId],
    queryFn: () => api.admin.getJobStatus(currentJobId!),
    enabled: !!currentJobId,
    refetchInterval: 2000,
  });

  useEffect(() => {
    if (jobStatus?.data?.status === "completed") {
      setCurrentJobId(null);
      queryClient.invalidateQueries({ queryKey: ["admin-predictions"] });
      toast.success("Predictions generated successfully");
    } else if (jobStatus?.data?.status === "failed") {
      setCurrentJobId(null);
      toast.error("Prediction generation failed");
    } else if (jobStatusError && currentJobId) {
      const timer = setTimeout(() => {
        setCurrentJobId(null);
        queryClient.invalidateQueries({ queryKey: ["admin-predictions"] });
        toast("Prediction generation started (job tracking unavailable)");
      }, 30000);
      return () => clearTimeout(timer);
    }
  }, [jobStatus, jobStatusError, queryClient, currentJobId]);

  async function remove(id: string) {
    if (!confirm(`Delete prediction ${id}?`)) return;
    setActionId(id);
    try {
      await deleteMutation.mutateAsync(id);
      setSelected((s) => {
        const copy = new Set(s);
        copy.delete(id);
        return copy;
      });
    } finally {
      setActionId(null);
    }
  }

  async function bulkDelete() {
    const ids = Array.from(selected);
    if (!ids.length || !confirm(`Delete ${ids.length} predictions?`)) return;
    await bulkDeleteMutation.mutateAsync(ids);
  }

  function ScorelineList({ predictionId }: { predictionId: string }) {
    const {
      data: detail,
      isPending,
      error: loadError,
    } = useQuery({
      queryKey: ["prediction-detail", predictionId],
      queryFn: () => api.getPredictionById(predictionId),
      staleTime: 300_000,
    });

    if (isPending || loadError || !detail)
      return <span className="text-xs text-muted-foreground">—</span>;
    const scorelines: Scoreline[] = detail.top_scorelines || [];
    if (!scorelines.length)
      return (
        <span className="text-xs text-muted-foreground">No scorelines</span>
      );

    return (
      <div className="flex flex-col gap-1">
        {scorelines.map((sl) => (
          <div
            key={`${sl.home_goals}-${sl.away_goals}`}
            className="flex items-center justify-between text-xs"
          >
            <span className="font-mono">
              {sl.home_goals} - {sl.away_goals}
            </span>
            <span className="text-muted-foreground">{pct(sl.probability)}</span>
          </div>
        ))}
      </div>
    );
  }

  if (error)
    return (
      <EmptyState
        title="Failed to load predictions"
        description={errMsg(error)}
      />
    );
  if (loading && !listResult)
    return <LoadingState message="Loading predictions..." />;
  if (!listResult || rows.length === 0)
    return <EmptyState title="No predictions found" />;

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <span className="text-sm text-muted-foreground">
          {total} predictions
        </span>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={forceRefresh}
              onChange={(e) => setForceRefresh(e.target.checked)}
            />
            Force refresh
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={clearAll}
              onChange={(e) => setClearAll(e.target.checked)}
            />
            Clear all
          </label>
          <Button
            variant="outline"
            onClick={() =>
              void generateMutation.mutate({
                clear_all: clearAll,
                include_research: true,
                limit: 50,
              })
            }
            disabled={generateMutation.isPending || !!currentJobId}
          >
            {generateMutation.isPending || currentJobId
              ? "Generating..."
              : "Generate predictions"}
          </Button>
          <Button
            variant="outline"
            onClick={() => void bulkDelete()}
            disabled={selected.size === 0 || bulkDeleteMutation.isPending}
          >
            {bulkDeleteMutation.isPending
              ? "Deleting..."
              : `Delete (${selected.size})`}
          </Button>
        </div>
      </div>

      <div className="overflow-x-auto rounded-xl border border-border/80">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="bg-muted/40">
              <th className="p-3">
                <Toggle
                  checked={allSelected}
                  onChange={(c) =>
                    setSelected(
                      c ? new Set(rows.map((p) => p.prediction_id)) : new Set(),
                    )
                  }
                />
              </th>
              <th className="px-3 py-2 font-medium">Match</th>
              <th className="px-3 py-2 font-medium">Model</th>
              <th className="px-3 py-2 font-medium">H</th>
              <th className="px-3 py-2 font-medium">D</th>
              <th className="px-3 py-2 font-medium">A</th>
              <th className="px-3 py-2 font-medium">Top 4 Scorelines</th>
              <th className="px-3 py-2 font-medium">Research</th>
              <th className="px-3 py-2 font-medium">AI Adj.</th>
              <th className="px-3 py-2 font-medium">Match Date</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((p: PredictionHistoryItem) => (
              <tr key={p.prediction_id} className="border-t border-border/60">
                <td className="p-3">
                  <Toggle
                    checked={selected.has(p.prediction_id)}
                    onChange={(c) =>
                      setSelected((s) => {
                        const copy = new Set(s);
                        if (c) {
                          copy.add(p.prediction_id);
                        } else {
                          copy.delete(p.prediction_id);
                        }
                        return copy;
                      })
                    }
                  />
                </td>
                <td className="px-3 py-2">
                  {p.match_home_team} vs {p.match_away_team}
                </td>
                <td className="px-3 py-2 font-mono text-xs">
                  {p.model_version}
                </td>
                <td className="px-3 py-2">{pct(p.home_probability)}</td>
                <td className="px-3 py-2">{pct(p.draw_probability)}</td>
                <td className="px-3 py-2">{pct(p.away_probability)}</td>
                <td className="px-3 py-2">
                  <ScorelineList predictionId={p.prediction_id} />
                </td>
                <td className="px-3 py-2">
                  {p.ai_adjustment_applied ? (
                    <span className="text-xs text-green-600">Yes</span>
                  ) : (
                    <span className="text-xs text-muted-foreground">—</span>
                  )}
                </td>
                <td className="px-3 py-2">
                  {p.ai_adjustment_applied ? (
                    <span className="text-xs text-green-600">Adjusted</span>
                  ) : (
                    <span className="text-xs text-muted-foreground">Base</span>
                  )}
                </td>
                <td className="px-3 py-2">
                  {p.match_kickoff
                    ? new Date(p.match_kickoff).toLocaleString()
                    : "—"}
                </td>
                <td className="px-3 py-2 text-right">
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={() => void remove(p.prediction_id)}
                    disabled={actionId === p.prediction_id}
                  >
                    {actionId === p.prediction_id ? (
                      "..."
                    ) : (
                      <Trash2 className="h-3 w-3" />
                    )}
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {rows.length > 0 && totalPages > 1 && (
        <Pagination
          page={page}
          pageSize={PAGE_SIZE}
          total={total}
          totalPages={totalPages}
          onPageChange={setPage}
          className="justify-center"
        />
      )}
    </div>
  );
}

export default function AdminPage() {
  return (
    <div className="space-y-6">
      <section className="surface-card rounded-[1.75rem] p-5 sm:p-6">
        <p className="section-kicker mb-2">Admin</p>
        <h1 className="text-3xl font-black tracking-[-0.06em] text-foreground">
          Admin Dashboard
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Manage leagues, teams, fixtures and predictions. Actions are
          authenticated with the admin API key and are irreversible.
        </p>
      </section>

      <Tabs defaultValue="leagues" className="space-y-4">
        <TabsList>
          <TabsTrigger value="leagues">Leagues</TabsTrigger>
          <TabsTrigger value="teams">Teams</TabsTrigger>
          <TabsTrigger value="fixtures">Fixtures</TabsTrigger>
          <TabsTrigger value="predictions">Predictions</TabsTrigger>
        </TabsList>
        <TabsContent value="leagues">
          <AdminLeagues />
        </TabsContent>
        <TabsContent value="teams">
          <AdminTeams />
        </TabsContent>
        <TabsContent value="fixtures">
          <FixturesTab />
        </TabsContent>
        <TabsContent value="predictions">
          <AdminPredictions />
        </TabsContent>
      </Tabs>
    </div>
  );
}

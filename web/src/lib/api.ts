import { env } from "@/lib/env";
import type {
  ApiResponse,
  ApiErrorResponse,
  ApiSuccessResponse,
  ApiResponseMeta,
} from "@/types/api";
import type {
  League,
  MatchBrief,
  MatchDetail,
  MatchSummary,
  PredictionDetail,
  PredictionHistoryItem,
  PredictionStats,
  ProviderStatus,
  ResearchData,
  SearchResultItem,
  Season,
  Standing,
  Team,
} from "@/types/models";

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public error_code?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function requestResponse<T>(
  path: string,
  options: RequestInit = {},
): Promise<ApiSuccessResponse<T>> {
  const url = `${env.apiUrl}${path}`;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 30000);

  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        ...options.headers,
      },
    });

    let data: ApiResponse<T> | null = null;
    const text = await response.text();
    if (text) {
      try {
        data = JSON.parse(text) as ApiResponse<T>;
      } catch {
        data = null;
      }
    }

    const isErrorResponse =
      data !== null &&
      typeof data === "object" &&
      "success" in data &&
      data.success === false;

    if (!response.ok || isErrorResponse) {
      const errorData = data as ApiErrorResponse | null;
      const errorMessage =
        errorData && errorData.error ? errorData.error.message : response.statusText || "Request failed";
      const errorCode =
        errorData && errorData.error ? errorData.error.code : "UNKNOWN_ERROR";

      throw new ApiError(errorMessage, response.status, errorCode);
    }

    return data as ApiSuccessResponse<T>;
  } catch (err) {
    if (err instanceof ApiError) throw err;
    if (err instanceof Error && err.name === "AbortError") {
      throw new ApiError("Request timeout", 408, "TIMEOUT");
    }
    throw new ApiError(
      err instanceof Error ? err.message : "Unknown error",
      500,
      "UNKNOWN_ERROR",
    );
  } finally {
    clearTimeout(timeoutId);
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  return (await requestResponse<T>(path, options)).data;
}

/**
 * Fetch a single resource.
 *
 * The provider endpoints return a uniform envelope where `data` is always a
 * list, even for a single-resource lookup, so unwrap the first element to match
 * the declared return type.
 */
async function requestOne<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const data = await request<T[]>(path, options);
  return (Array.isArray(data) ? data[0] : data) as T;
}

export interface PaginatedResult<T> {
  data: T[];
  meta: {
    page: number;
    page_size: number;
    total: number;
    total_pages: number;
  };
}

export interface AdminLeague {
  id: string;
  provider_league_id: string | null;
  name: string;
  country: string | null;
  country_code: string | null;
  is_active: boolean;
  created_at: string | null;
}

export interface AdminTeam {
  id: string;
  provider_team_id: string | null;
  league_id: string | null;
  name: string;
  short_name: string | null;
  country: string | null;
  is_active: boolean;
  created_at: string | null;
  match_count: number;
}

type QsValue = string | number | boolean | undefined | null;
type QsRecord = Record<string, QsValue | QsValue[]>;

function buildQs(params: QsRecord): string {
  const sp = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null) continue;
    if (Array.isArray(value)) {
      for (const item of value) {
        if (item !== undefined && item !== null && item !== "") {
          sp.append(key, String(item));
        }
      }
    } else if (value !== "") {
      sp.append(key, String(value));
    }
  }
  const qs = sp.toString();
  return qs ? `?${qs}` : "";
}

function adminHeaders(): Record<string, string> {
  return { "X-Admin-Api-Key": env.adminApiKey };
}

type AdminEnvelope<T = unknown> = {
  success: boolean;
  data?: T | null;
  meta?: { message?: string; [key: string]: unknown };
  error?: { code?: string; message?: string; details?: unknown };
  detail?: string;
};

async function adminCall<T = unknown>(
  path: string,
  init: RequestInit = {},
): Promise<ApiSuccessResponse<T>> {
  // Admin endpoints return the standard envelope but (a) fail with useful
  // `meta.message` bodies on 200 `success:false` and (b) `{ detail }` on
  // HTTP errors. `requestResponse` doesn't surface those, so we handle the
  // envelope explicitly here to give the UI actionable error text.
  const url = `${env.apiUrl}${path}`;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 30000);
  try {
    const response = await fetch(url, {
      ...init,
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        ...init.headers,
        "X-Admin-Api-Key": env.adminApiKey,
      },
    });

    let data: AdminEnvelope<T> | null = null;
    const text = await response.text();
    if (text) {
      try {
        data = JSON.parse(text) as AdminEnvelope<T>;
      } catch {
        data = null;
      }
    }

    const isFailure = data !== null && data.success === false;

    if (!response.ok || isFailure) {
      const message =
        data?.meta?.message ||
        data?.error?.message ||
        data?.detail ||
        response.statusText ||
        "Request failed";
      throw new ApiError(message, response.status);
    }
    return {
      success: true,
      data: data?.data ?? null,
      meta: (data?.meta ?? undefined) as ApiResponseMeta | undefined,
    } as ApiSuccessResponse<T>;
  } catch (err) {
    if (err instanceof ApiError) throw err;
    if (err instanceof Error && err.name === "AbortError") {
      throw new ApiError("Request timeout", 408, "TIMEOUT");
    }
    throw new ApiError(
      err instanceof Error ? err.message : "Unknown error",
      500,
      "UNKNOWN_ERROR",
    );
  } finally {
    clearTimeout(timeoutId);
  }
}

async function requestPaginated<T>(
  path: string,
  options: RequestInit = {},
): Promise<PaginatedResult<T>> {
  const response = await requestResponse<T[]>(path, options);

  const meta = response.meta || {};
  return {
    data: response.data,
    meta: {
      page: Number(meta.page) || 1,
      page_size: Number(meta.page_size) || 20,
      total: Number(meta.total) || 0,
      total_pages: Number(meta.total_pages) || 1,
    },
  };
}

export const api = {
  // Health
  health: () => request<{ status: string; checks: Record<string, unknown> }>(
    "/api/v1/health",
  ),
  healthDeep: () =>
    request<{ status: string; checks: Record<string, unknown> }>(
      "/api/v1/health/deep",
    ),

  // Providers
  providerStatus: () =>
    request<ProviderStatus>("/api/v1/providers/status"),

  // Leagues
  listLeagues: (params?: {
    is_active?: boolean;
    country?: string;
    page?: number;
    page_size?: number;
  }) => {
    const search = new URLSearchParams();
    if (params?.is_active !== undefined) search.set("is_active", String(params.is_active));
    if (params?.country) search.set("country", params.country);
    if (params?.page) search.set("page", String(params.page));
    if (params?.page_size) search.set("page_size", String(params.page_size));
    const qs = search.toString();
    return requestPaginated<League>(`/api/v1/providers/leagues${qs ? `?${qs}` : ""}`);
  },
  getLeague: (
    id: string,
    params?: { include?: string },
  ) => {
    const qs = params?.include
      ? `?include=${encodeURIComponent(params.include)}`
      : "";
    return requestOne<{
      id: string;
      name: string;
      country: string | null;
      country_code: string | null;
      is_active: boolean;
      created_at: string | null;
      current_season: Record<string, unknown> | null;
      currentseason?: Record<string, unknown> | null;
      country_details?: Record<string, unknown> | null;
      sport?: Record<string, unknown> | null;
      stages?: unknown[];
      seasons?: Season[];
      standings?: Standing[];
      teams?: Team[];
    }>(`/api/v1/providers/leagues/${id}${qs}`);
  },
  getLeagueSeasons: (id: string, params?: { is_current?: boolean; page?: number; page_size?: number }) => {
    const search = new URLSearchParams();
    search.set("league_id", id);
    if (params?.is_current !== undefined) search.set("is_current", String(params.is_current));
    if (params?.page) search.set("page", String(params.page));
    if (params?.page_size) search.set("page_size", String(params.page_size));
    const qs = search.toString();
    return requestPaginated<{
      id: string;
      league_id: string;
      name: string;
      year: number | null;
      start_date: string | null;
      end_date: string | null;
      is_current: boolean;
    }>(`/api/v1/providers/leagues/seasons?${qs}`);
  },
  getLeagueStandings: (id: string, params?: { season_id?: string; page?: number; page_size?: number }) => {
    const search = new URLSearchParams();
    if (params?.season_id) search.set("season_id", params.season_id);
    if (params?.page) search.set("page", String(params.page));
    if (params?.page_size) search.set("page_size", String(params.page_size));
    const qs = search.toString();
    return requestPaginated<{
      team_id: string | null;
      team_name: string;
      position: number;
      points: number;
      played: number;
      wins: number;
      draws: number;
      losses: number;
      goals_for: number;
      goals_against: number;
      goal_difference: number;
      form: string | null;
    }>(`/api/v1/providers/leagues/${id}/standings${qs ? `?${qs}` : ""}`);
  },

  // Teams
  listTeams: (params?: {
    league_id?: string;
    is_active?: boolean;
    search?: string;
    include?: string;
    page?: number;
    page_size?: number;
  }) => {
    const search = new URLSearchParams();
    if (params?.league_id) search.set("league_id", params.league_id);
    if (params?.is_active !== undefined) search.set("is_active", String(params.is_active));
    if (params?.search) search.set("search", params.search);
    if (params?.include) search.set("include", params.include);
    if (params?.page) search.set("page", String(params.page));
    if (params?.page_size) search.set("page_size", String(params.page_size));
    const qs = search.toString();
    return requestPaginated<Team>(`/api/v1/providers/teams${qs ? `?${qs}` : ""}`);
  },
  getTeam: (id: string, params?: { include?: string }) => {
    const qs = params?.include ? `?include=${encodeURIComponent(params.include)}` : "";
    return requestOne<Team>(`/api/v1/providers/teams/${id}${qs}`);
  },
  getTeamMatches: (id: string, params?: {
    league_id?: string;
    status?: string;
    date_from?: string;
    date_to?: string;
    page?: number;
    page_size?: number;
  }) => {
    const search = new URLSearchParams();
    if (params?.league_id) search.set("league_id", params.league_id);
    if (params?.status) search.set("status", params.status);
    if (params?.date_from) search.set("date_from", params.date_from);
    if (params?.date_to) search.set("date_to", params.date_to);
    if (params?.page) search.set("page", String(params.page));
    if (params?.page_size) search.set("page_size", String(params.page_size));
    const qs = search.toString();
    return requestPaginated<MatchBrief>(`/api/v1/providers/teams/${id}/matches${qs ? `?${qs}` : ""}`);
  },
  getTeamStats: (id: string, params?: { league_id?: string; season_id?: string }) => {
    const search = new URLSearchParams();
    if (params?.league_id) search.set("league_id", params.league_id);
    if (params?.season_id) search.set("season_id", params.season_id);
    const qs = search.toString();
    return request<{
      team_id: string;
      statistics: Array<Record<string, unknown>>;
    }>(`/api/v1/providers/teams/${id}/statistics${qs ? `?${qs}` : ""}`);
  },
  getTeamSeasons: (id: string) =>
    request<{ success: boolean; data: Array<{
      id: string;
      league_id: string;
      league_name: string;
      name: string;
      year: number | null;
      start_date: string | null;
      end_date: string | null;
      is_current: boolean;
    }>; meta: { total: number } }>(`/api/v1/teams/${id}/seasons`),
  getTeamCountries: (id: string) =>
    request<{ success: boolean; data: Array<{ country: string; league_count: number }>; meta: { total: number } }>(`/api/v1/teams/${id}/countries`),
  getLeagueTeams: (leagueId: string, params?: { page?: number; page_size?: number }) => {
    const search = new URLSearchParams();
    if (params?.page) search.set("page", String(params.page));
    if (params?.page_size) search.set("page_size", String(params.page_size));
    const qs = search.toString();
    return requestPaginated<Team>(`/api/v1/teams/leagues/${leagueId}/teams${qs ? `?${qs}` : ""}`);
  },

  // Matches
  listMatches: (params?: {
    date?: string;
    date_from?: string;
    date_to?: string;
    league_id?: string;
    season_id?: string;
    team_id?: string;
    status?: string;
    country?: string;
    provider?: string;
    upcoming?: boolean;
    today?: boolean;
    page?: number;
    page_size?: number;
  }) => {
    const search = new URLSearchParams();
    Object.entries(params || {}).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        search.set(key, String(value));
      }
    });
    const qs = search.toString();
    return requestPaginated<MatchBrief>(`/api/v1/providers/matches${qs ? `?${qs}` : ""}`);
  },
  getTodayMatches: (params?: { league_id?: string; page?: number; page_size?: number }) => {
    const search = new URLSearchParams();
    if (params?.league_id) search.set("league_id", params.league_id);
    if (params?.page) search.set("page", String(params.page));
    if (params?.page_size) search.set("page_size", String(params.page_size));
    const qs = search.toString();
    return requestPaginated<MatchBrief>(`/api/v1/providers/matches/today${qs ? `?${qs}` : ""}`);
  },
  getUpcomingMatches: (params?: {
    days?: number;
    league_id?: string;
    team_id?: string;
    page?: number;
    page_size?: number;
  }) => {
    const search = new URLSearchParams();
    if (params?.days) search.set("days", String(params.days));
    if (params?.league_id) search.set("league_id", params.league_id);
    if (params?.team_id) search.set("team_id", params.team_id);
    if (params?.page) search.set("page", String(params.page));
    if (params?.page_size) search.set("page_size", String(params.page_size));
    const qs = search.toString();
    return requestPaginated<MatchBrief>(`/api/v1/providers/matches/upcoming${qs ? `?${qs}` : ""}`);
  },
  getMatch: (id: string) => requestOne<MatchDetail>(`/api/v1/matches/${id}`),
  getMatchSummary: (id: string) => requestOne<MatchSummary>(`/api/v1/providers/matches/${id}/summary`),

  // Predictions
  getPrediction: (matchId: string) =>
    request<{ data: PredictionDetail }>(`/api/v1/matches/${matchId}/prediction`),
  getPredictions: (params?: {
    match_id?: string;
    league_id?: string;
    team_id?: string;
    model_version?: string;
    date_from?: string;
    date_to?: string;
    upcoming_only?: boolean;
    page?: number;
    page_size?: number;
  }) => {
    const search = new URLSearchParams();
    Object.entries(params || {}).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        search.set(key, String(value));
      }
    });
    const qs = search.toString();
    return requestPaginated<PredictionHistoryItem>(`/api/v1/predictions${qs ? `?${qs}` : ""}`);
  },
  getPredictionById: (id: string) => request<{
    prediction_id: string;
    match_id: string;
    match_kickoff?: string | null;
    model_version: string;
    prediction_version: string;
    generated_at: string | null;
    provider_used: string;
    lambda_home: number | null;
    lambda_away: number | null;
    home_probability: number | null;
    draw_probability: number | null;
    away_probability: number | null;
    over_2_5_probability: number | null;
    under_2_5_probability: number | null;
    btts_probability: number | null;
    confidence: number | null;
    prediction_status: string;
    feature_snapshot: Record<string, unknown>;
    news_snapshot: Record<string, unknown>;
    odds_snapshot: Record<string, unknown>;
    ai_explanation: string | null;
    ai_evidence: unknown;
    ai_adjustment: unknown;
    source_ids: string[];
    top_scorelines: Array<{
      rank: number;
      home_goals: number;
      away_goals: number;
      probability: number;
    }>;
  }>(`/api/v1/predictions/${id}`),
  getMatchPredictions: (matchId: string, params?: { page?: number; page_size?: number }) => {
    const search = new URLSearchParams();
    if (params?.page) search.set("page", String(params.page));
    if (params?.page_size) search.set("page_size", String(params.page_size));
    const qs = search.toString();
    return requestPaginated<Record<string, unknown>>(`/api/v1/matches/${matchId}/predictions${qs ? `?${qs}` : ""}`);
  },
  compareMatchPredictions: (matchId: string) =>
    request<{ current: unknown; changes: Record<string, unknown> }>(
      `/api/v1/matches/${matchId}/predictions/compare`,
    ),
  getPredictionStats: () => request<PredictionStats>("/api/v1/predictions/stats"),

  // Research
  getResearch: (matchId: string, params?: { force_refresh?: boolean }) => {
    const search = new URLSearchParams();
    if (params?.force_refresh !== undefined) search.set("force_refresh", String(params.force_refresh));
    const qs = search.toString();
    return request<ResearchData>(`/api/v1/matches/${matchId}/research${qs ? `?${qs}` : ""}`);
  },
  getAnalysis: (matchId: string) => request<PredictionDetail>(`/api/v1/matches/${matchId}/analysis`),

  // Search
  search: (params: {
    q: string;
    type?: string;
    league_id?: string;
    limit?: number;
  }) => {
    const search = new URLSearchParams();
    search.set("q", params.q);
    if (params.type) search.set("type", params.type);
    if (params.league_id) search.set("league_id", params.league_id);
    if (params.limit) search.set("limit", String(params.limit));
    const qs = search.toString();
    return request<{
      teams: SearchResultItem[];
      leagues: SearchResultItem[];
      matches: SearchResultItem[];
      predictions: SearchResultItem[];
      players: SearchResultItem[];
    }>(`/api/v1/search?${qs}`);
  },

  // Admin — all calls send the X-Admin-Api-Key header.
  admin: {
    listLeagues: (params?: {
      page?: number;
      page_size?: number;
      search?: string;
      is_active?: boolean;
    }) => {
      const qs = buildQs({
        page: params?.page,
        page_size: params?.page_size,
        search: params?.search,
        is_active: params?.is_active,
      });
      return requestPaginated<AdminLeague>(
        `/api/v1/admin/leagues${qs}`,
        { headers: adminHeaders() },
      );
    },
    listTeams: (params?: {
      page?: number;
      page_size?: number;
      search?: string;
      league_id?: string;
    }) => {
      const qs = buildQs({
        page: params?.page,
        page_size: params?.page_size,
        search: params?.search,
        league_id: params?.league_id,
      });
      return requestPaginated<AdminTeam>(
        `/api/v1/admin/teams${qs}`,
        { headers: adminHeaders() },
      );
    },
    listPredictions: (params?: {
      match_id?: string;
      league_id?: string;
      team_id?: string;
      model_version?: string;
      date_from?: string;
      date_to?: string;
      upcoming_only?: boolean;
      page?: number;
      page_size?: number;
    }) => {
      const qs = buildQs(params || {});
      return requestPaginated<PredictionHistoryItem>(
        `/api/v1/predictions${qs}`,
      );
    },
    deleteLeague: (id: string) =>
      adminCall<{ deleted: number; league_id: string }>(
        `/api/v1/admin/leagues/${encodeURIComponent(id)}`,
        { method: "DELETE" },
      ),
    deleteLeagues: (ids: string[]) =>
      adminCall<{ deleted: number; league_ids: string[] }>(
        `/api/v1/admin/leagues${buildQs({ ids })}`,
        { method: "DELETE" },
      ),
    deleteTeam: (id: string) =>
      adminCall<{ deleted: number; team_id: string }>(
        `/api/v1/admin/teams/${encodeURIComponent(id)}`,
        { method: "DELETE" },
      ),
    deleteTeams: (ids: string[]) =>
      adminCall<{ deleted: number; team_ids: string[] }>(
        `/api/v1/admin/teams${buildQs({ ids })}`,
        { method: "DELETE" },
      ),
    deletePrediction: (id: string) =>
      adminCall<{ deleted: number; prediction_id: string }>(
        `/api/v1/admin/predictions/${encodeURIComponent(id)}`,
        { method: "DELETE" },
      ),
    deletePredictions: (ids: string[]) =>
      adminCall<{ deleted: number; prediction_ids: string[] }>(
        `/api/v1/admin/predictions${buildQs({ ids })}`,
        { method: "DELETE" },
      ),
    resyncLeague: (id: string) =>
      adminCall<Record<string, number>>(
        `/api/v1/admin/leagues/${encodeURIComponent(id)}/resync`,
        { method: "POST" },
      ),
    resyncTeam: (id: string) =>
      adminCall<Record<string, number>>(
        `/api/v1/admin/teams/${encodeURIComponent(id)}/resync`,
        { method: "POST" },
      ),
    resyncFixtures: (params: {
      date_from?: string;
      date_to?: string;
      league_id?: string;
    }) =>
      adminCall<Record<string, number>>(
        `/api/v1/admin/fixtures/resync${buildQs({
          date_from: params?.date_from,
          date_to: params?.date_to,
          league_id: params?.league_id,
        })}`,
        { method: "POST" },
      ),
    fetchLeagues: () =>
      adminCall<{ synced: boolean; leagues: number }>(
        "/api/v1/providers/sync/leagues",
        { method: "POST" },
      ),
    fetchTeams: (params: { league_id: string; season_id: string }) =>
      adminCall<{ synced: boolean; teams: number }>(
        `/api/v1/providers/sync/teams${buildQs({
          league_id: params.league_id,
          season_id: params.season_id,
        })}`,
        { method: "POST" },
      ),
    generatePredictions: (params?: {
      league_ids?: string[];
      force_refresh?: boolean;
      clear_all?: boolean;
      include_research?: boolean;
      limit?: number;
    }) =>
      adminCall<{ job_id: string; status: string }>(
        `/api/v1/admin/predictions/generate${buildQs({
          league_ids: params?.league_ids,
          force_refresh: params?.force_refresh,
          clear_all: params?.clear_all,
          include_research: params?.include_research,
          limit: params?.limit,
        })}`,
          { method: "POST" },
      ),
    getJobStatus: (jobId: string) =>
      request<{
        success: boolean;
        data: {
          job_id: string;
          status: string;
          succeeded?: number;
          failed?: number;
          total?: number;
          errors?: string[];
          extra?: Record<string, unknown>;
        };
      }>(`/api/v1/predictions/jobs/${jobId}`),
  },
};

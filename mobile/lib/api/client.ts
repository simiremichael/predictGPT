import { env } from "../env";
import { ApiError } from "./errors";
import type {
  ApiResponse,
  ApiErrorResponse,
  PaginatedResponse,
  PaginatedMeta,
  League,
  Team,
  MatchBrief,
  MatchDetail,
  MatchSummary,
  PredictionDetail,
  PredictionHistoryItem,
  PredictionStats,
  ResearchData,
  SearchResultItem,
  ProviderStatus,
  Standing,
} from "@/types";

export { ApiError } from "./errors";

interface CacheOptions {
  ttl?: number;
}

interface FetchOptions {
  cache?: CacheOptions;
}

class ApiClient {
  private baseURL: string;

  constructor(baseURL: string) {
    this.baseURL = baseURL;
  }

  private async requestResponse<T>(
    path: string,
    options: RequestInit = {},
  ): Promise<ApiErrorResponse | { success: true; data: T; meta?: Record<string, unknown> }> {
    const url = `${this.baseURL}${path}`;

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

      const data = await response.json();

      if (!response.ok || (data as { success?: boolean }).success === false) {
        throw new ApiError(
          (data as { error?: { message?: string } }).error?.message || response.statusText,
          response.status,
          (data as { error?: { code?: string } }).error?.code,
        );
      }

      return data as { success: true; data: T; meta?: Record<string, unknown> };
    } catch (err) {
      if (err instanceof ApiError) throw err;
      if (err instanceof DOMException && err.name === "AbortError") {
        throw new ApiError("Request timeout", 408, "TIMEOUT");
      }
      throw new ApiError(
        err instanceof Error ? err.message : "Network error",
        500,
        "UNKNOWN_ERROR",
      );
    } finally {
      clearTimeout(timeoutId);
    }
  }

  private async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const response = await this.requestResponse<T>(path, options);
    return response.data;
  }

  private async requestPaginated<T>(
    path: string,
    options: RequestInit = {},
  ): Promise<{ data: T[]; meta: PaginatedMeta }> {
    const response = await this.requestResponse<T[]>(path, options);
    const meta = response.meta || {};
    return {
      data: response.data as unknown as T[],
      meta: {
        page: Number(meta.page) || 1,
        page_size: Number(meta.page_size) || 20,
        total: Number(meta.total) || 0,
        total_pages: Number(meta.total_pages) || 1,
      },
    };
  }

  // ─── Health ─────────────────────────────────────────── //
  health = () =>
    this.request<{ status: string; checks: Record<string, unknown> }>(
      "/api/v1/health",
    );

  healthDeep = () =>
    this.request<{ status: string; checks: Record<string, unknown> }>(
      "/api/v1/health/deep",
    );

  // ─── Providers ──────────────────────────────────────── //
  providerStatus = () =>
    this.request<ProviderStatus>("/api/v1/providers/status");

  // ─── Leagues ────────────────────────────────────────── //
  listLeagues = (params?: {
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
    return this.requestPaginated<League>(
      `/api/v1/leagues${qs ? `?${qs}` : ""}`,
    );
  };

  getLeague = (id: string, params?: {
    include_teams?: boolean;
    include_fixtures?: boolean;
    include_standings?: boolean;
  }) => {
    const search = new URLSearchParams();
    if (params?.include_teams) search.set("include_teams", "true");
    if (params?.include_fixtures) search.set("include_fixtures", "true");
    if (params?.include_standings) search.set("include_standings", "true");
    const qs = search.toString();
    return this.request<League>(
      `/api/v1/leagues/${id}${qs ? `?${qs}` : ""}`,
    );
  };

  getLeagueSeasons = (id: string, params?: {
    is_current?: boolean;
    page?: number;
    page_size?: number;
  }) => {
    const search = new URLSearchParams();
    if (params?.is_current !== undefined) search.set("is_current", String(params.is_current));
    if (params?.page) search.set("page", String(params.page));
    if (params?.page_size) search.set("page_size", String(params.page_size));
    const qs = search.toString();
    return this.requestPaginated<{
      id: string;
      league_id: string;
      name: string;
      year: number | null;
      start_date: string | null;
      end_date: string | null;
      is_current: boolean;
    }>(`/api/v1/leagues/${id}/seasons${qs ? `?${qs}` : ""}`);
  };

  getLeagueStandings = (id: string, params?: {
    season_id?: string;
    page?: number;
    page_size?: number;
  }) => {
    const search = new URLSearchParams();
    if (params?.season_id) search.set("season_id", params.season_id);
    if (params?.page) search.set("page", String(params.page));
    if (params?.page_size) search.set("page_size", String(params.page_size));
    const qs = search.toString();
    return this.requestPaginated<{
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
    }>(`/api/v1/leagues/${id}/standings${qs ? `?${qs}` : ""}`);
  };

  getCountryLeagues = (country: string) => {
    return this.request<{
      success: boolean;
      data: League[];
      meta: { country: string; total_leagues: number };
    }>(`/api/v1/leagues/country/${encodeURIComponent(country)}`);
  };

  getLeagues = (params?: {
    is_active?: boolean;
    country?: string;
    page?: number;
    page_size?: number;
  }) => this.listLeagues(params);

  getCountryLeaguesList = (country: string) =>
    this.getCountryLeagues(country).then((res) => ({
      data: res.data,
      meta: res.meta,
    }));

  // ─── Teams ──────────────────────────────────────────── //
  listTeams = (params?: {
    league_id?: string;
    is_active?: boolean;
    search?: string;
    page?: number;
    page_size?: number;
  }) => {
    const urlSearch = new URLSearchParams();
    if (params?.league_id) urlSearch.set("league_id", params.league_id);
    if (params?.is_active !== undefined) urlSearch.set("is_active", String(params.is_active));
    if (params?.search) urlSearch.set("search", params.search);
    if (params?.page) urlSearch.set("page", String(params.page));
    if (params?.page_size) urlSearch.set("page_size", String(params.page_size));
    const qs = urlSearch.toString();
    return this.requestPaginated<Team>(
      `/api/v1/teams${qs ? `?${qs}` : ""}`,
    );
  };

  getTeam = (id: string) =>
    this.request<Team>(`/api/v1/teams/${id}`);

  getTeamMatches = (id: string, params?: {
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
    return this.requestPaginated<MatchBrief>(
      `/api/v1/teams/${id}/matches${qs ? `?${qs}` : ""}`,
    );
  };

  getTeamStats = (id: string, params?: { league_id?: string; season_id?: string }) => {
    const search = new URLSearchParams();
    if (params?.league_id) search.set("league_id", params.league_id);
    if (params?.season_id) search.set("season_id", params.season_id);
    const qs = search.toString();
    return this.request<{
      team_id: string;
      statistics: Array<Record<string, unknown>>;
    }>(`/api/v1/teams/${id}/statistics${qs ? `?${qs}` : ""}`);
  };

  // ─── Matches ────────────────────────────────────────── //
  listMatches = (params?: {
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
    return this.requestPaginated<MatchBrief>(
      `/api/v1/matches${qs ? `?${qs}` : ""}`,
    );
  };

  getTodayMatches = (params?: {
    league_id?: string;
    page?: number;
    page_size?: number;
  }) => {
    const search = new URLSearchParams();
    if (params?.league_id) search.set("league_id", params.league_id);
    if (params?.page) search.set("page", String(params.page));
    if (params?.page_size) search.set("page_size", String(params.page_size));
    const qs = search.toString();
    return this.requestPaginated<MatchBrief>(
      `/api/v1/matches/today${qs ? `?${qs}` : ""}`,
    );
  };

  getUpcomingMatches = (params?: {
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
    return this.requestPaginated<MatchBrief>(
      `/api/v1/matches/upcoming${qs ? `?${qs}` : ""}`,
    );
  };

  getMatch = (id: string) =>
    this.request<MatchDetail>(`/api/v1/matches/${id}`);

  getMatchSummary = (id: string) =>
    this.request<MatchSummary>(`/api/v1/matches/${id}/summary`);

  // ─── Predictions ────────────────────────────────────── //
  getPrediction = (matchId: string) =>
    this.request<{ data: PredictionDetail }>(
      `/api/v1/matches/${matchId}/prediction`,
    );

  getMatchPrediction = (matchId: string) => this.getPrediction(matchId);

  listPredictions = (params?: {
    match_id?: string;
    league_id?: string;
    team_id?: string;
    model_version?: string;
    date_from?: string;
    date_to?: string;
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
    return this.requestPaginated<PredictionHistoryItem>(
      `/api/v1/predictions${qs ? `?${qs}` : ""}`,
    );
  };

  getPredictionById = (id: string) =>
    this.request<PredictionDetail>(`/api/v1/predictions/${id}`);

  getMatchPredictions = (matchId: string) =>
    this.requestPaginated<PredictionDetail>(
      `/api/v1/matches/${matchId}/predictions`,
    );

  compareMatchPredictions = (matchId: string) =>
    this.request<{ current: unknown; changes: Record<string, unknown> }>(
      `/api/v1/matches/${matchId}/predictions/compare`,
    );

  getPredictionStats = () =>
    this.request<PredictionStats>("/api/v1/predictions/stats");

  getPredictionHistory = (params?: {
    match_id?: string;
    league_id?: string;
    team_id?: string;
    model_version?: string;
    date_from?: string;
    date_to?: string;
    page?: number;
    page_size?: number;
  }) => this.listPredictions(params);

  // ─── Research ───────────────────────────────────────── //
  getResearch = (matchId: string) =>
    this.request<ResearchData>(
      `/api/v1/matches/${matchId}/research`,
    );

  getAnalysis = (matchId: string) =>
    this.request<{ data: PredictionDetail }>(
      `/api/v1/matches/${matchId}/analysis`,
    );

  // ─── Search ─────────────────────────────────────────── //
  search = (params: {
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
    return this.request<{
      teams: SearchResultItem[];
      leagues: SearchResultItem[];
      matches: SearchResultItem[];
      predictions: SearchResultItem[];
    }>(`/api/v1/search?${qs}`);
  };

}

export type { SearchResultItem };

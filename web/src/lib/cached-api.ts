import { env } from "@/lib/env";
import { LEAGUE_TAG, MATCH_TAG, TEAM_TAG, PREDICTION_TAG } from "@/lib/cache-tags";
import type {
  League,
  MatchBrief,
  Team,
  PredictionHistoryItem,
  PredictionStats,
} from "@/types/models";

export { LEAGUE_TAG, MATCH_TAG, TEAM_TAG, PREDICTION_TAG };

export interface PaginatedResponse<T> {
  data: T[];
  meta: {
    page: number;
    page_size: number;
    total: number;
    total_pages: number;
    is_subscribed?: boolean;
    free_predictions_remaining?: number | null;
    [key: string]: unknown;
  };
  [key: string]: unknown;
}

async function fetchWithTags<T>(path: string, tags: string[]): Promise<T> {
  const response = await fetch(`${env.apiUrl}${path}`, {
    next: { tags },
  });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }
  const body: { data?: T | T[]; success?: boolean; error?: { message?: string } } = await response.json();
  if (body.success === false) {
    throw new Error(body.error?.message || response.statusText || "Request failed");
  }
  if (body.data === undefined) return body as T;
  return (Array.isArray(body.data) ? body.data[0] : body.data) as T;
}

async function fetchWithTagsPaginated<T>(path: string, tags: string[]): Promise<PaginatedResponse<T>> {
  const response = await fetch(`${env.apiUrl}${path}`, {
    next: { tags },
  });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }
  const body: { success?: boolean; data?: T[]; meta?: Record<string, unknown>; error?: { message?: string } } = await response.json();
  if (body.success === false) {
    throw new Error(body.error?.message || response.statusText || "Request failed");
  }
  return {
    data: body.data ?? [],
    meta: {
      page: Number(body.meta?.page) || 1,
      page_size: Number(body.meta?.page_size) || 20,
      total: Number(body.meta?.total) || 0,
      total_pages: Number(body.meta?.total_pages) || 1,
      ...(body.meta?.is_subscribed !== undefined
        ? { is_subscribed: body.meta.is_subscribed as boolean }
        : {}),
      ...(body.meta?.free_predictions_remaining !== undefined
        ? { free_predictions_remaining: body.meta.free_predictions_remaining as number | null }
        : {}),
    },
  };
}

export async function fetchCachedLeagues(params?: {
  page?: number;
  page_size?: number;
  country?: string;
  is_active?: boolean;
}): Promise<PaginatedResponse<League>> {
  const sp = new URLSearchParams();
  if (params?.page) sp.set("page", String(params.page));
  if (params?.page_size) sp.set("page_size", String(params.page_size));
  if (params?.country) sp.set("country", params.country);
  if (params?.is_active !== undefined) sp.set("is_active", String(params.is_active));
  const qs = sp.toString();
  return fetchWithTagsPaginated<League>(
    `/api/v1/providers/leagues${qs ? `?${qs}` : ""}`,
    [LEAGUE_TAG]
  );
}

export async function fetchCachedLeague(id: string): Promise<League> {
  return fetchWithTags<League>(`/api/v1/providers/leagues/${id}`, [LEAGUE_TAG, `${LEAGUE_TAG}-${id}`]);
}

export async function fetchCachedTeams(params?: {
  page?: number;
  page_size?: number;
  league_id?: string;
  search?: string;
}): Promise<PaginatedResponse<Team>> {
  const sp = new URLSearchParams();
  if (params?.page) sp.set("page", String(params.page));
  if (params?.page_size) sp.set("page_size", String(params.page_size));
  if (params?.league_id) sp.set("league_id", params.league_id);
  if (params?.search) sp.set("search", params.search);
  const qs = sp.toString();
  return fetchWithTagsPaginated<Team>(
    `/api/v1/providers/teams${qs ? `?${qs}` : ""}`,
    [TEAM_TAG]
  );
}

export async function fetchCachedTeam(id: string): Promise<Team> {
  return fetchWithTags<Team>(`/api/v1/providers/teams/${id}`, [TEAM_TAG, `${TEAM_TAG}-${id}`]);
}

export async function fetchCachedMatches(params?: {
  page?: number;
  page_size?: number;
  date?: string;
  date_from?: string;
  date_to?: string;
  league_id?: string;
  team_id?: string;
  status?: string;
  today?: boolean;
  upcoming?: boolean;
}): Promise<PaginatedResponse<MatchBrief>> {
  const sp = new URLSearchParams();
  if (params?.page) sp.set("page", String(params.page));
  if (params?.page_size) sp.set("page_size", String(params.page_size));
  if (params?.date) sp.set("date", params.date);
  if (params?.date_from) sp.set("date_from", params.date_from);
  if (params?.date_to) sp.set("date_to", params.date_to);
  if (params?.league_id) sp.set("league_id", params.league_id);
  if (params?.team_id) sp.set("team_id", params.team_id);
  if (params?.status) sp.set("status", params.status);
  if (params?.today) sp.set("today", "true");
  if (params?.upcoming) sp.set("upcoming", "true");
  const qs = sp.toString();
  return fetchWithTagsPaginated<MatchBrief>(
    `/api/v1/providers/matches${qs ? `?${qs}` : ""}`,
    [MATCH_TAG]
  );
}

export async function fetchCachedTodayMatches(params?: {
  page?: number;
  page_size?: number;
  league_id?: string;
}): Promise<PaginatedResponse<MatchBrief>> {
  const sp = new URLSearchParams();
  if (params?.page) sp.set("page", String(params.page));
  if (params?.page_size) sp.set("page_size", String(params.page_size));
  if (params?.league_id) sp.set("league_id", params.league_id);
  const qs = sp.toString();
  return fetchWithTagsPaginated<MatchBrief>(
    `/api/v1/providers/matches/today${qs ? `?${qs}` : ""}`,
    [MATCH_TAG, "today-matches"]
  );
}

export async function fetchCachedUpcomingMatches(params?: {
  page?: number;
  page_size?: number;
  league_id?: string;
  team_id?: string;
  days?: number;
}): Promise<PaginatedResponse<MatchBrief>> {
  const sp = new URLSearchParams();
  if (params?.page) sp.set("page", String(params.page));
  if (params?.page_size) sp.set("page_size", String(params.page_size));
  if (params?.league_id) sp.set("league_id", params.league_id);
  if (params?.team_id) sp.set("team_id", params.team_id);
  if (params?.days) sp.set("days", String(params.days));
  const qs = sp.toString();
  return fetchWithTagsPaginated<MatchBrief>(
    `/api/v1/providers/matches/upcoming${qs ? `?${qs}` : ""}`,
    [MATCH_TAG, "upcoming-matches"]
  );
}

export async function fetchCachedPredictions(params?: {
  page?: number;
  page_size?: number;
  match_id?: string;
  league_id?: string;
  team_id?: string;
  kickoff_date?: string;
  played?: boolean;
  upcoming_only?: boolean;
  min_elapsed_minutes?: number;
  max_elapsed_minutes?: number;
  newest_first?: boolean;
}): Promise<PaginatedResponse<PredictionHistoryItem>> {
  const sp = new URLSearchParams();
  if (params?.page) sp.set("page", String(params.page));
  if (params?.page_size) sp.set("page_size", String(params.page_size));
  if (params?.match_id) sp.set("match_id", params.match_id);
  if (params?.league_id) sp.set("league_id", params.league_id);
  if (params?.team_id) sp.set("team_id", params.team_id);
  if (params?.kickoff_date) sp.set("kickoff_date", params.kickoff_date);
  if (params?.played !== undefined) sp.set("played", String(params.played));
  if (params?.upcoming_only !== undefined) sp.set("upcoming_only", String(params.upcoming_only));
  if (params?.min_elapsed_minutes !== undefined) {
    sp.set("min_elapsed_minutes", String(params.min_elapsed_minutes));
  }
  if (params?.max_elapsed_minutes !== undefined) {
    sp.set("max_elapsed_minutes", String(params.max_elapsed_minutes));
  }
  if (params?.newest_first !== undefined) {
    sp.set("newest_first", String(params.newest_first));
  }
  const qs = sp.toString();
  return fetchWithTagsPaginated<PredictionHistoryItem>(
    `/api/v1/predictions${qs ? `?${qs}` : ""}`,
    [PREDICTION_TAG]
  );
}

export async function fetchCachedPredictionStats(): Promise<PredictionStats> {
  return fetchWithTags<PredictionStats>("/api/v1/predictions/stats", [PREDICTION_TAG]);
}

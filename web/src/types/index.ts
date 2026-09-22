export interface MatchStatistics {
  possession?: Record<string, unknown> | null;
  shots?: Record<string, unknown> | null;
  shots_on_target?: Record<string, unknown> | null;
  xg?: Record<string, unknown> | null;
  xga?: Record<string, unknown> | null;
  corners?: Record<string, unknown> | null;
  fouls?: Record<string, unknown> | null;
}

export interface TeamStatistics {
  team_id?: string | null;
  league_id?: string | null;
  season_id?: string | null;
  is_home: boolean;
  games_played?: number | null;
  wins?: number | null;
  draws?: number | null;
  losses?: number | null;
  goals_for?: number | null;
  goals_against?: number | null;
  clean_sheets?: number | null;
  points?: number | null;
  position?: number | null;
  form_rating?: number | null;
  average_possession?: number | null;
  average_shots?: number | null;
  average_xg?: number | null;
  average_xga?: number | null;
  goals_per_game?: number | null;
  goals_conceded_per_game?: number | null;
}

export interface ResearchEvidence {
  subject: string;
  claim: string | null;
  evidence_status: string;
  confidence: number;
  source_ids: string[];
}

export interface ResearchSource {
  url: string;
  title?: string | null;
  publisher?: string | null;
  published_at?: string | null;
  source_type?: string | null;
  credibility_score: number;
  freshness_score: number;
}

export interface ResearchData {
  match_id: string;
  researched_at?: string | null;
  sources: ResearchSource[];
  injuries: ResearchEvidence[];
  suspensions: ResearchEvidence[];
  lineups: Array<Record<string, unknown>>;
  team_news: ResearchEvidence[];
  conflicts: Array<Record<string, unknown>>;
  data_quality: number;
}

export interface JobStatus {
  job_id: string;
  status: string;
  message: string;
}

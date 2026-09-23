// Shared types for the Football AI mobile application
// These mirror the backend API response structures

export interface ApiResponse<T> {
  success: boolean;
  data: T;
  meta?: Record<string, unknown>;
}

export interface ApiErrorResponse {
  success: false;
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
}

export interface PaginatedMeta {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export interface PaginatedResponse<T> {
  success: boolean;
  data: T[];
  meta: PaginatedMeta;
}

export interface League {
  id: string;
  name: string;
  country: string | null;
  country_code: string | null;
  is_active: boolean;
  created_at: string | null;
  tier?: number | null;
  current_season?: Season | null;
  team_count?: number;
  standings_summary?: Standing[];
}

export interface Season {
  id: string;
  league_id: string;
  name: string | null;
  year: number | null;
  start_date: string | null;
  end_date: string | null;
  is_current: boolean;
  created_at: string | null;
}

export interface Standing {
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
  clean_sheets?: number;
  form_rating?: number | null;
  average_possession?: number | null;
  average_xg?: number | null;
  average_xga?: number | null;
}

export interface Team {
  id: string;
  name: string;
  short_name: string | null;
  slug: string | null;
  logo_url: string | null;
  venue_name: string | null;
  venue_city: string | null;
  country: string | null;
  is_active: boolean;
  created_at: string | null;
}

export interface TeamStatistics {
  id: string;
  team_name: string;
  league_id: string;
  season_id: string | null;
  is_home: boolean | null;
  games_played: number;
  wins: number;
  draws: number;
  losses: number;
  goals_for: number;
  goals_against: number;
  clean_sheets: number;
  points: number;
  position: number | null;
  form_rating: number | null;
  average_possession: number | null;
  average_shots: number | null;
  average_xg: number | null;
  average_xga: number | null;
  goals_per_game: number | null;
  goals_conceded_per_game: number | null;
  retrieved_at: string | null;
}

export interface MatchBrief {
  id: string;
  league_id: string | null;
  league_name: string | null;
  season_id: string | null;
  home_team_id: string | null;
  home_team_name: string | null;
  away_team_id: string | null;
  away_team_name: string | null;
  kickoff_at: string | null;
  status: string;
  venue: string | null;
  home_score: number | null;
  away_score: number | null;
  is_finished: boolean;
  retrieved_at: string | null;
}

export interface MatchDetail {
  id: string;
  league_id: string | null;
  league_name: string | null;
  season_id: string | null;
  home_team_id: string | null;
  home_team_name: string | null;
  away_team_id: string | null;
  away_team_name: string | null;
  kickoff_at: string | null;
  status: string;
  venue: string | null;
  referee: string | null;
  home_score: number | null;
  away_score: number | null;
  is_finished: boolean;
  statistics: Record<string, unknown> | null;
  form: Record<string, unknown> | null;
  h2h: Record<string, unknown> | null;
  injuries: Array<Record<string, unknown>>;
  suspensions: Array<Record<string, unknown>>;
  lineups: Array<Record<string, unknown>>;
  odds: Record<string, unknown> | null;
  retrieved_at: string | null;
  league?: League | null;
  season?: Season | null;
  home_team: { id: string; name: string; logo_url?: string | null; venue_city?: string | null } | null;
  away_team: { id: string; name: string; logo_url?: string | null; venue_city?: string | null } | null;
  home_team_full?: Team;
  away_team_full?: Team;
}

export interface MatchSummary {
  match: MatchBrief;
  prediction?: Prediction | null;
  data_quality: {
    football: number;
  };
}

export interface Scoreline {
  home_goals: number;
  away_goals: number;
  probability: number;
  rank?: number;
}

export interface ScoreMatrix {
  home_max_goals: number;
  away_max_goals: number;
  matrix: number[][];
}

export interface ResultProbabilities {
  home: number;
  draw: number;
  away: number;
}

export interface MarketOverUnder {
  over_0_5: number;
  over_1_5: number;
  over_2_5: number;
  over_3_5: number;
  over_4_5: number;
  under_0_5: number;
  under_1_5: number;
  under_2_5: number;
  under_3_5: number;
  under_4_5: number;
}

export interface MarketBTT {
  yes: number;
  no: number;
}

export interface MarketCleanSheet {
  home_clean_sheet: number;
  away_clean_sheet: number;
}

export interface MarketDoubleChance {
  home_or_draw: number;
  draw_or_away: number;
  home_or_away: number;
}

export interface Markets {
  over_under: MarketOverUnder;
  btts: MarketBTT;
  clean_sheets: MarketCleanSheet;
  double_chance: MarketDoubleChance;
}

export interface ExpectedGoals {
  home: number;
  away: number;
}

export interface GoalDistribution {
  probabilities: number[];
  mean: number;
}

export interface GoalDistributions {
  home: GoalDistribution;
  away: GoalDistribution;
}

export interface AIAdjustment {
  applied: boolean;
  version?: string | null;
  home_attack_adjustment: number;
  away_attack_adjustment: number;
  home_defense_adjustment: number;
  away_defense_adjustment: number;
  confidence: number;
  reason_codes: string[];
  source_ids: string[];
}

export interface PredictionScoreline {
  rank: number;
  home_goals: number;
  away_goals: number;
  probability: number;
}

export interface PredictionDetail {
  prediction_id: string;
  match_id: string;
  model: string;
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
  context_hash?: string | null;
  top_scorelines: PredictionScoreline[];
  markets: Markets;
  result_probabilities: ResultProbabilities;
  score_matrix?: ScoreMatrix | null;
  goal_distributions?: GoalDistributions | null;
  expected_goals?: ExpectedGoals | null;
  research: ResearchSummary;
  ai_adjustment_detail?: AIAdjustment;
}

export interface Prediction {
  match: MatchBrief;
  prediction: PredictionDetail | null;
  data_quality: {
    football: number;
  };
}

export interface PredictionSummary {
  prediction_id: string;
  match: MatchBrief;
  prediction: PredictionSummaryDetail | null;
  data_quality: {
    football: number;
  };
}

export interface PredictionSummaryDetail {
  prediction_id: string;
  match_id: string;
  model_version: string;
  home_probability: number | null;
  draw_probability: number | null;
  away_probability: number | null;
  model_confidence: number | null;
  top_scoreline: { home_goals: number; away_goals: number; probability: number } | null;
  expected_goals: { home: number; away: number } | null;
}

export interface PredictionHistoryItem {
  prediction_id: string;
  match_id: string;
  match_home_team: string;
  match_away_team: string;
  model_version: string;
  prediction_version: string;
  generated_at: string | null;
  data_quality: number;
  model_confidence: number;
  home_probability: number | null;
  draw_probability: number | null;
  away_probability: number | null;
  ai_adjustment_applied: boolean;
  context_hash?: string | null;
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
  title: string | null;
  publisher: string | null;
  published_at: string | null;
  source_type: string | null;
  credibility_score: number;
  freshness_score: number;
}

export interface ResearchData {
  match_id: string;
  researched_at: string | null;
  sources: ResearchSource[];
  injuries: ResearchEvidence[];
  suspensions: ResearchEvidence[];
  lineups: Array<Record<string, unknown>>;
  team_news: ResearchEvidence[];
  conflicts: Array<Record<string, unknown>>;
  data_quality: number;
}

export interface ResearchSummary {
  available: boolean;
  data_quality: number;
  sources_count: number;
  injuries_count: number;
  suspensions_count: number;
  lineups_count: number;
  team_news_count: number;
  conflicts_count: number;
  average_credibility: number;
  average_freshness: number;
  researched_at?: string | null;
}

export interface SearchResultItem {
  id: string;
  type: string;
  name: string;
  subtitle?: string | null;
  logo_url?: string | null;
  country?: string | null;
  home_team_name?: string | null;
  away_team_name?: string | null;
  kickoff_at?: string | null;
  status?: string | null;
  home_score?: number | null;
  away_score?: number | null;
  is_finished?: boolean;
  model_version?: string | null;
  prediction_version?: string | null;
  generated_at?: string | null;
}

export interface PredictionStats {
  total_predictions: number;
  predictions_by_model: Record<string, number>;
  average_data_quality: number | null;
  last_prediction_at: string | null;
}

export interface ProviderStatus {
  active_provider: string;
  providers: Record<string, Record<string, unknown>>;
}

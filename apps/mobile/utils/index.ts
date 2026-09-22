export {
  formatDate,
  formatTime,
  formatProbability,
  formatDateTime,
  timeToKickoff,
  getMatchStatusColor,
  getMatchStatusLabel,
  getConfidenceColor,
  getEvidenceStatusColor,
  formatDataQuality,
  getDataQualityLabel,
  truncateText,
  getLeagueTierLabel,
  getLeagueName,
  LEAGUE_TIERS,
} from "./format";

export const MATCH_STATUS_COLORS: Record<string, { bg: string; text: string }> = {
  scheduled: { bg: "bg-blue-500/10", text: "text-blue-600" },
  live: { bg: "bg-red-500/10", text: "text-red-600" },
  finished: { bg: "bg-gray-500/10", text: "text-gray-600" },
  paused: { bg: "bg-yellow-500/10", text: "text-yellow-600" },
  postponed: { bg: "bg-orange-500/10", text: "text-orange-600" },
  cancelled: { bg: "bg-red-500/10", text: "text-red-600" },
};

export const BREAKPOINTS = {
  sm: 640,
  md: 768,
  lg: 1024,
  xl: 1280,
  "2xl": 1536,
} as const;

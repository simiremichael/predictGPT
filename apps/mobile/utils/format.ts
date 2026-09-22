import { format, formatDistanceToNow, isToday, isTomorrow, isYesterday } from "date-fns";

export function formatDate(date: string | Date): string {
  const d = typeof date === "string" ? new Date(date) : date;
  if (isToday(d)) return "Today";
  if (isTomorrow(d)) return "Tomorrow";
  if (isYesterday(d)) return "Yesterday";
  return format(d, "MMM d, yyyy");
}

export function formatDateTime(date: string | Date): string {
  const d = typeof date === "string" ? new Date(date) : date;
  return format(d, "MMM d, yyyy 'at' h:mm a");
}

export function formatTime(date: string | Date): string {
  const d = typeof date === "string" ? new Date(date) : date;
  return format(d, "h:mm a");
}

export function timeToKickoff(date: string | Date): string {
  const d = typeof date === "string" ? new Date(date) : date;
  const diff = d.getTime() - Date.now();
  if (diff < 0) return "Started";
  if (diff < 60000) return "Starting now";
  return formatDistanceToNow(d, { addSuffix: true });
}

export function formatProbability(prob: number | null | undefined): string {
  if (prob === null || prob === undefined) return "-";
  return `${Math.round(prob * 100)}%`;
}

export function formatGoals(lambda: number | null | undefined): string {
  if (lambda === null || lambda === undefined) return "-";
  return lambda.toFixed(2);
}

export function formatScoreline(home: number, away: number): string {
  return `${home}-${away}`;
}

export function getMatchStatusLabel(status: string): string {
  switch (status.toLowerCase()) {
    case "scheduled":
      return "Scheduled";
    case "live":
      return "Live";
    case "finished":
    case "full_time":
      return "Finished";
    case "paused":
      return "Paused";
    case "postponed":
      return "Postponed";
    case "cancelled":
      return "Cancelled";
    case "suspended":
      return "Suspended";
    default:
      return status;
  }
}

export function getMatchStatusColor(status: string): {
  bg: string;
  text: string;
} {
  switch (status.toLowerCase()) {
    case "scheduled":
      return { bg: "bg-blue-500/10", text: "text-blue-600" };
    case "live":
      return { bg: "bg-red-500/10", text: "text-red-600" };
    case "finished":
    case "full_time":
      return { bg: "bg-gray-500/10", text: "text-gray-600" };
    case "paused":
      return { bg: "bg-yellow-500/10", text: "text-yellow-600" };
    case "postponed":
      return { bg: "bg-orange-500/10", text: "text-orange-600" };
    case "cancelled":
      return { bg: "bg-red-500/10", text: "text-red-600" };
    default:
      return { bg: "bg-muted", text: "text-muted-foreground" };
  }
}

export function getConfidenceColor(confidence: number): {
  bg: string;
  text: string;
  label: string;
} {
  if (confidence >= 0.8)
    return { bg: "bg-emerald-500/10", text: "text-emerald-600", label: "High" };
  if (confidence >= 0.6)
    return { bg: "bg-blue-500/10", text: "text-blue-600", label: "Medium-high" };
  if (confidence >= 0.4)
    return { bg: "bg-amber-500/10", text: "text-amber-600", label: "Medium" };
  return { bg: "bg-rose-500/10", text: "text-rose-600", label: "Low" };
}

export function getEvidenceStatusColor(status: string): {
  bg: string;
  text: string;
  label: string;
} {
  const normalized = status.toLowerCase();
  if (normalized === "confirmed")
    return { bg: "bg-green-500/10", text: "text-green-600", label: "Confirmed" };
  if (normalized === "reported")
    return { bg: "bg-amber-500/10", text: "text-amber-600", label: "Reported" };
  if (normalized === "uncertain" || normalized === "unverified")
    return { bg: "bg-gray-500/10", text: "text-gray-600", label: "Uncertain" };
  if (normalized === "speculation")
    return { bg: "bg-blue-500/10", text: "text-blue-600", label: "Speculation" };
  return { bg: "bg-muted", text: "text-muted-foreground", label: status };
}

export function formatDataQuality(quality: number | null | undefined): string {
  if (quality === null || quality === undefined) return "—";
  return `${Math.round(quality * 100)}%`;
}

export function getDataQualityLabel(quality: number | null | undefined): string {
  if (quality === null || quality === undefined) return "Unknown";
  if (quality >= 0.8) return "High";
  if (quality >= 0.6) return "Medium";
  if (quality >= 0.4) return "Low";
  return "Insufficient";
}

export function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return `${text.slice(0, maxLength - 3)}...`;
}

export function getLeagueTierLabel(tier: number | undefined | null): string {
  if (tier === undefined || tier === null) return "";
  if (tier === 1) return "1st Division";
  if (tier === 2) return "2nd Division";
  if (tier === 3) return "3rd Division";
  return `${tier}th Division`;
}

export function getLeagueName(leagueId: string): string {
  const label = LEAGUE_TIERS[leagueId];
  return label || leagueId.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase());
}

export const LEAGUE_TIERS: Record<string, string> = {
  premier_league: "Premier League",
  championship: "EFL Championship",
  la_liga: "La Liga",
  segunda_division: "Segunda División",
  serie_a: "Serie A",
  serie_b: "Serie B",
  bundesliga: "Bundesliga",
  ligue_1: "Ligue 1",
  ligue_2: "Ligue 2",
  primeira_liga: "Primeira Liga",
  super_lig: "Süper Lig",
  champions_league: "UEFA Champions League",
  europa_league: "UEFA Europa League",
  conference_league: "UEFA Conference League",
};

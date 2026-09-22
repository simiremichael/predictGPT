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

export function formatProbability(prob: number): string {
  return `${Math.round(prob * 100)}%`;
}

export function formatGoals(lambdas: number): string {
  return lambdas.toFixed(2);
}

export function formatScoreline(home: number, away: number): string {
  return `${home}-${away}`;
}

export function getMatchStatusColor(status: string): string {
  switch (status.toLowerCase()) {
    case "scheduled":
      return "bg-blue-500/10 text-blue-600";
    case "live":
      return "bg-red-500/10 text-red-600";
    case "finished":
    case "full_time":
      return "bg-gray-500/10 text-gray-600";
    case "paused":
      return "bg-yellow-500/10 text-yellow-600";
    case "postponed":
      return "bg-orange-500/10 text-orange-600";
    case "cancelled":
      return "bg-red-500/10 text-red-600";
    default:
      return "bg-muted text-muted-foreground";
  }
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

export function getConfidenceColor(confidence: number): {
  bg: string;
  text: string;
  label: string;
} {
  if (confidence >= 0.8) return { bg: "bg-emerald-500/10", text: "text-emerald-600", label: "High" };
  if (confidence >= 0.6) return { bg: "bg-blue-500/10", text: "text-blue-600", label: "Medium-high" };
  if (confidence >= 0.4) return { bg: "bg-amber-500/10", text: "text-amber-600", label: "Medium" };
  return { bg: "bg-rose-500/10", text: "text-rose-600", label: "Low" };
}

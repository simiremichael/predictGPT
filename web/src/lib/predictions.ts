import type { PredictionDetail } from "@/types/models";

export function getConfidenceColor(
  confidence: number,
): { bg: string; text: string; label: string } {
  if (confidence >= 0.8) return { bg: "bg-emerald-500/10", text: "text-emerald-600", label: "High" };
  if (confidence >= 0.6) return { bg: "bg-blue-500/10", text: "text-blue-600", label: "Medium-high" };
  if (confidence >= 0.4) return { bg: "bg-amber-500/10", text: "text-amber-600", label: "Medium" };
  return { bg: "bg-rose-500/10", text: "text-rose-600", label: "Low" };
}

export function getColorForProbability(prob: number): string {
  if (prob >= 0.5) return "#10b981";
  if (prob >= 0.35) return "#3b82f6";
  if (prob >= 0.2) return "#f59e0b";
  return "#ef4444";
}

export function getResultColor(
  prob: number,
  _isHighest: boolean,
): { color: string; label: string } {
  if (prob >= 0.5) return { color: "#10b981", label: "Likely" };
  if (prob >= 0.35) return { color: "#3b82f6", label: "Possible" };
  if (prob >= 0.2) return { color: "#f59e0b", label: "Unlikely" };
  return { color: "#ef4444", label: "Very unlikely" };
}

export function getPredictionOutcome(pred: PredictionDetail): {
  result: "home" | "draw" | "away";
  probability: number;
} {
  const probs = pred.result_probabilities;
  if (probs.home >= probs.draw && probs.home >= probs.away) {
    return { result: "home", probability: probs.home };
  }
  if (probs.draw >= probs.away) {
    return { result: "draw", probability: probs.draw };
  }
  return { result: "away", probability: probs.away };
}

export function getScoreMatrixMaxValue(matrix: number[][]): number {
  return Math.max(...matrix.flat());
}

export function formatScorelineString(home: number, away: number): string {
  return `${home} - ${away}`;
}

export function getTeamDisplayName(name: string | undefined | null): string {
  if (!name) return "TBD";
  return name.length > 20 ? `${name.slice(0, 18)}..` : name;
}

export function getInitials(name: string | undefined | null): string {
  if (!name) return "??";
  const parts = name.split(" ").filter(Boolean);
  if (parts.length === 0) return "??";
  if (parts.length === 1) return parts[0].charAt(0).toUpperCase();
  return (parts[0].charAt(0) + parts[parts.length - 1].charAt(0)).toUpperCase();
}

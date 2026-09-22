import { cn } from "@/lib/utils";
import type { Scoreline } from "@/types/models";
import { getColorForProbability } from "@/lib/predictions";

interface TopScorelinesProps {
  scorelines: Scoreline[];
  className?: string;
  showRank?: boolean;
}

export function TopScorelines({
  scorelines,
  className,
  showRank = true,
}: TopScorelinesProps) {
  const maxProb = Math.max(...scorelines.map((s) => s.probability), 0.001);

  return (
    <div className={cn("space-y-2", className)}>
      {scorelines.map((sl, idx) => {
        const color = getColorForProbability(sl.probability);
        return (
          <div
            key={`${sl.home_goals}-${sl.away_goals}`}
            className="flex items-center gap-3"
          >
            {showRank && (
              <div className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-bold">
                {idx + 1}
              </div>
            )}
            <div className="font-mono text-sm">
              {sl.home_goals} - {sl.away_goals}
            </div>
            <div className="flex-1">
              <div className="h-2 rounded-full bg-muted">
                <div
                  className="h-full rounded-full transition-all"
                  style={{
                    width: `${(sl.probability / maxProb) * 100}%`,
                    backgroundColor: color,
                  }}
                />
              </div>
            </div>
            <div className="w-12 text-right text-sm font-bold">
              {Math.round(sl.probability * 100)}%
            </div>
          </div>
        );
      })}
    </div>
  );
}

interface GoalDistributionProps {
  distribution: number[];
  mean: number;
  label: string;
  className?: string;
  maxGoals?: number;
}

export function GoalDistribution({
  distribution,
  mean,
  label,
  className,
  maxGoals = 8,
}: GoalDistributionProps) {
  const maxProb = Math.max(...distribution, 0.001);

  return (
    <div className={cn("space-y-2", className)}>
      <div className="text-sm font-medium">{label}</div>
      <div className="space-y-1">
        {distribution.slice(0, maxGoals + 1).map((prob, i) => (
          <div key={i} className="flex items-center gap-2">
            <span className="w-4 text-xs">{i}</span>
            <div className="flex-1 h-4 rounded bg-muted">
              <div
                className="h-full rounded bg-primary transition-all"
                style={{ width: `${(prob / maxProb) * 100}%` }}
              />
            </div>
            <span className="w-10 text-right text-xs">
              {(prob * 100).toFixed(1)}%
            </span>
          </div>
        ))}
      </div>
      <div className="text-xs text-muted-foreground">
        Mean (λ): {mean.toFixed(2)}
      </div>
    </div>
  );
}

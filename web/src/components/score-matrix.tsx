import { cn } from "@/lib/utils";
import { getColorForProbability } from "@/lib/predictions";
import type { ScoreMatrix } from "@/types/models";

interface ScoreMatrixProps {
  matrix: ScoreMatrix;
  maxGoals?: number;
  homeTeam: string;
  awayTeam: string;
  highlightTop4?: Array<{ home_goals: number; away_goals: number }>;
  className?: string;
}

export function ScoreMatrixGrid({
  matrix,
  maxGoals = 5,
  homeTeam,
  awayTeam,
  highlightTop4 = [],
  className,
}: ScoreMatrixProps) {
  const maxProb = Math.max(...matrix.matrix.flat(), 0.001);

  const isHighlighted = (home: number, away: number) =>
    highlightTop4.some(
      (s) => s.home_goals === home && s.away_goals === away,
    );

  return (
    <div className={cn("w-full max-w-lg overflow-x-auto", className)}>
      <div className="text-center text-xs font-medium text-muted-foreground mb-2">
        Home: {homeTeam} | Away: {awayTeam}
      </div>
      <div className="grid" style={{ gridTemplateColumns: `40px repeat(${maxGoals + 1}, 1fr)` }}>
        <div />
        <div
          className="text-center text-xs font-medium text-muted-foreground"
          style={{ writingMode: "vertical-rl", transform: "rotate(180deg)" }}
        >
          {awayTeam}
        </div>
        {Array.from({ length: maxGoals + 1 }).map((_, i) => (
          <div
            key={i}
            className="text-center text-xs font-medium text-muted-foreground"
          >
            {i}
          </div>
        ))}

        {Array.from({ length: maxGoals + 1 }).map((_, homeIdx) => (
          <>
            <div
              key={`label-${homeIdx}`}
              className="text-center text-xs font-medium text-muted-foreground"
            >
              {homeIdx}
            </div>
            {Array.from({ length: maxGoals + 1 }).map((_, awayIdx) => {
              const prob = matrix.matrix[homeIdx]?.[awayIdx] ?? 0;
              const intensity = prob / maxProb;
              const color = getColorForProbability(prob);
              const highlighted = isHighlighted(homeIdx, awayIdx);

              return (
                <div
                  key={`${homeIdx}-${awayIdx}`}
                  className={cn(
                    "aspect-square rounded text-center text-xs font-medium transition-all",
                    highlighted && "ring-2 ring-primary",
                  )}
                  style={{
                    backgroundColor: `${color}${Math.round(intensity * 70).toString(16).padStart(2, "0")}`,
                    color: prob > maxProb * 0.3 ? "#ffffff" : "#000000",
                    minWidth: "32px",
                  }}
                  title={`${homeIdx}-${awayIdx}: ${(prob * 100).toFixed(1)}%`}
                >
                  {prob > 0.01 ? `${(prob * 100).toFixed(0)}%` : ""}
                </div>
              );
            })}
          </>
        ))}
      </div>
      <div className="mt-2 text-center text-xs text-muted-foreground">
        Home goals
      </div>
    </div>
  );
}

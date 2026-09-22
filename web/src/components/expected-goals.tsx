import { cn } from "@/lib/utils";
import type { ExpectedGoals } from "@/types/models";

interface ExpectedGoalsProps {
  xg: ExpectedGoals;
  homeTeam: string;
  awayTeam: string;
  lambdaHome?: number;
  lambdaAway?: number;
  className?: string;
}

export function ExpectedGoalsDisplay({
  xg,
  homeTeam,
  awayTeam,
  lambdaHome,
  lambdaAway,
  className,
}: ExpectedGoalsProps) {
  const maxXg = Math.max(xg.home, xg.away, 0.1);

  const barWidth = (value: number) =>
    `${Math.max((value / maxXg) * 100, 5)}%`;

  return (
    <div className={cn("space-y-3", className)}>
      <div className="flex items-end justify-between gap-4">
        <div className="w-2/5">
          <div className="mb-1 text-sm font-medium">{homeTeam}</div>
          <div className="h-6 rounded-lg bg-muted">
            <div
              className="h-full rounded-lg bg-primary transition-all"
              style={{ width: barWidth(xg.home) }}
            />
          </div>
        </div>
        <div className="text-2xl font-bold text-muted-foreground">vs</div>
        <div className="w-2/5">
          <div className="mb-1 text-sm font-medium text-right">{awayTeam}</div>
          <div className="h-6 rounded-lg bg-muted">
            <div
              className="h-full rounded-lg bg-secondary transition-all"
              style={{
                width: barWidth(xg.away),
                marginLeft: "auto",
              }}
            />
          </div>
        </div>
      </div>

      <div className="flex justify-between text-xs text-muted-foreground">
        <span>
          xG: {xg.home.toFixed(2)}
          {lambdaHome !== undefined && (
            <span className="ml-1 opacity-60">(λ: {lambdaHome.toFixed(2)})</span>
          )}
        </span>
        <span>
          xG: {xg.away.toFixed(2)}
          {lambdaAway !== undefined && (
            <span className="ml-1 opacity-60">(λ: {lambdaAway.toFixed(2)})</span>
          )}
        </span>
      </div>
    </div>
  );
}

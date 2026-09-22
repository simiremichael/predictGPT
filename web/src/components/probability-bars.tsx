import { cn } from "@/lib/utils";
import { getColorForProbability } from "@/lib/predictions";

interface ProbabilityBarsProps {
  home: number;
  draw: number;
  away: number;
  homeTeam: string;
  awayTeam: string;
  className?: string;
  showLabels?: boolean;
}

export function ProbabilityBars({
  home,
  draw,
  away,
  homeTeam,
  awayTeam,
  className,
  showLabels = true,
}: ProbabilityBarsProps) {
  const homeColor = getColorForProbability(home);
  const drawColor = getColorForProbability(draw);
  const awayColor = getColorForProbability(away);

  const maxProb = Math.max(home, draw, away);

  return (
    <div className={cn("space-y-2", className)}>
      {showLabels && (
        <div className="flex justify-between text-xs text-muted-foreground">
          <span>{homeTeam}</span>
          <span>Draw</span>
          <span>{awayTeam}</span>
        </div>
      )}
      <div className="flex items-center gap-2">
        <div
          className="h-8 w-1/3 rounded-lg transition-all"
          style={{
            width: `${(home / maxProb) * 100}%`,
            backgroundColor: `${homeColor}30`,
            minWidth: "40px",
          }}
        >
          <div
            className="flex h-full items-center justify-center rounded-lg text-xs font-bold"
            style={{ color: homeColor }}
          >
            {Math.round(home * 100)}%
          </div>
        </div>
        <div
          className="h-8 w-1/3 rounded-lg transition-all"
          style={{
            width: `${(draw / maxProb) * 100}%`,
            backgroundColor: `${drawColor}30`,
            minWidth: "40px",
          }}
        >
          <div
            className="flex h-full items-center justify-center rounded-lg text-xs font-bold"
            style={{ color: drawColor }}
          >
            {Math.round(draw * 100)}%
          </div>
        </div>
        <div
          className="h-8 w-1/3 rounded-lg transition-all"
          style={{
            width: `${(away / maxProb) * 100}%`,
            backgroundColor: `${awayColor}30`,
            minWidth: "40px",
          }}
        >
          <div
            className="flex h-full items-center justify-center rounded-lg text-xs font-bold"
            style={{ color: awayColor }}
          >
            {Math.round(away * 100)}%
          </div>
        </div>
      </div>
    </div>
  );
}

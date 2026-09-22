import { cn } from "@/lib/utils";
import type { Markets } from "@/types/models";

interface MarketsDisplayProps {
  markets: Markets;
  className?: string;
}

export function MarketsDisplay({ markets, className }: MarketsDisplayProps) {
  return (
    <div className={cn("grid gap-4 sm:grid-cols-2", className)}>
      <div className="space-y-2">
        <h4 className="text-sm font-semibold">Over/Under 2.5</h4>
        <div className="flex justify-between text-sm">
          <span>Over 2.5: {(markets.over_under.over_2_5 * 100).toFixed(1)}%</span>
          <span>Under 2.5: {(markets.over_under.under_2_5 * 100).toFixed(1)}%</span>
        </div>
      </div>

      <div className="space-y-2">
        <h4 className="text-sm font-semibold">Both Teams to Score</h4>
        <div className="flex justify-between text-sm">
          <span>Yes: {(markets.btts.yes * 100).toFixed(1)}%</span>
          <span>No: {(markets.btts.no * 100).toFixed(1)}%</span>
        </div>
      </div>

      <div className="space-y-2">
        <h4 className="text-sm font-semibold">Clean Sheets</h4>
        <div className="flex justify-between text-sm">
          <span>Home: {(markets.clean_sheets.home_clean_sheet * 100).toFixed(1)}%</span>
          <span>Away: {(markets.clean_sheets.away_clean_sheet * 100).toFixed(1)}%</span>
        </div>
      </div>

      <div className="space-y-2">
        <h4 className="text-sm font-semibold">Double Chance</h4>
        <div className="flex justify-between text-sm">
          <span>X or 2: {(markets.double_chance.draw_or_away * 100).toFixed(1)}%</span>
          <span>1 or 2: {(markets.double_chance.home_or_away * 100).toFixed(1)}%</span>
        </div>
      </div>
    </div>
  );
}

export function OverUnderChart({ markets }: { markets: Markets }) {
  const thresholds = [
    { label: "0.5", over: markets.over_under.over_0_5, under: markets.over_under.under_0_5 },
    { label: "1.5", over: markets.over_under.over_1_5, under: markets.over_under.under_1_5 },
    { label: "2.5", over: markets.over_under.over_2_5, under: markets.over_under.under_2_5 },
    { label: "3.5", over: markets.over_under.over_3_5, under: markets.over_under.under_3_5 },
    { label: "4.5", over: markets.over_under.over_4_5, under: markets.over_under.under_4_5 },
  ];

  return (
    <div className="space-y-2">
      <h4 className="text-sm font-semibold mb-2">Over/Under by Total</h4>
      {thresholds.map((t) => (
        <div key={t.label} className="flex items-center gap-2">
          <span className="w-8 text-xs">O/U {t.label}</span>
          <div className="flex-1">
            <div className="h-4 rounded bg-muted">
              <div
                className="h-full rounded bg-primary"
                style={{ width: `${t.over * 100}%` }}
              />
            </div>
          </div>
          <span className="w-12 text-right text-xs font-medium">
            {(t.over * 100).toFixed(0)}%
          </span>
          <div className="flex-1">
            <div className="h-4 rounded bg-muted">
              <div
                className="h-full rounded bg-secondary"
                style={{ width: `${t.under * 100}%` }}
              />
            </div>
          </div>
          <span className="w-12 text-right text-xs font-medium">
            {(t.under * 100).toFixed(0)}%
          </span>
        </div>
      ))}
    </div>
  );
}

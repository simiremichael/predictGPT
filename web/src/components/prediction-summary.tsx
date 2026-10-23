import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { AIGeneratedBadge } from "@/components/ai-generated-badge";
import type { PredictionDetail } from "@/types/models";
import {
  getConfidenceColor,
  getPredictionOutcome,
} from "@/lib/predictions";

interface PredictionSummaryProps {
  prediction: PredictionDetail;
  className?: string;
  showMatchInfo?: boolean;
}

export function PredictionSummary({
  prediction,
  className,
  showMatchInfo = true,
}: PredictionSummaryProps) {
  const outcome = getPredictionOutcome(prediction);
  const confidenceInfo = getConfidenceColor(prediction.model_confidence);

  return (
    <div
      className={cn(
        "rounded-xl border border-border bg-card p-4 shadow-sm",
        className,
      )}
    >
      {showMatchInfo && (
        <div className="mb-3 text-center">
          <h3 className="min-w-0 text-balance font-semibold">
            <span className="[overflow-wrap:anywhere]">{prediction.match_home_team}</span>{" "}
            <span className="whitespace-nowrap text-muted-foreground">vs</span>{" "}
            <span className="[overflow-wrap:anywhere]">{prediction.match_away_team}</span>
          </h3>
          <p className="text-xs text-muted-foreground">
            {prediction.match_kickoff
              ? new Date(prediction.match_kickoff).toLocaleString()
              : new Date(prediction.generated_at).toLocaleDateString()}
          </p>
        </div>
      )}

      <div className="grid grid-cols-3 gap-2 text-center">
        <div>
          <div className="text-xs text-muted-foreground">Home</div>
          <div className="text-xl font-bold">
            {Math.round(prediction.result_probabilities.home * 100)}%
          </div>
          {outcome.result === "home" && (
            <Badge variant="default" className="mt-1 text-xs">
              Pick
            </Badge>
          )}
        </div>
        <div>
          <div className="text-xs text-muted-foreground">Draw</div>
          <div className="text-xl font-bold">
            {Math.round(prediction.result_probabilities.draw * 100)}%
          </div>
          {outcome.result === "draw" && (
            <Badge variant="default" className="mt-1 text-xs">
              Pick
            </Badge>
          )}
        </div>
        <div>
          <div className="text-xs text-muted-foreground">Away</div>
          <div className="text-xl font-bold">
            {Math.round(prediction.result_probabilities.away * 100)}%
          </div>
          {outcome.result === "away" && (
            <Badge variant="default" className="mt-1 text-xs">
              Pick
            </Badge>
          )}
        </div>
      </div>

      {prediction.top_scoreline && (
        <div className="mt-3 text-center">
          <div className="text-sm text-muted-foreground">
            Most likely score:
          </div>
          <div className="text-lg font-bold">
            {prediction.top_scoreline.home_goals} -{" "}
            {prediction.top_scoreline.away_goals}
          </div>
          <div className="text-xs text-muted-foreground">
            ({Math.round(prediction.top_scoreline.probability * 100)}% prob)
          </div>
        </div>
      )}

      <div className="mt-3 flex flex-col gap-2 border-t border-border pt-2 text-xs sm:flex-row sm:items-center sm:justify-between sm:gap-3">
        <AIGeneratedBadge />
        <Badge
          variant="outline"
          className={cn(
            "text-xs",
            confidenceInfo.bg,
            confidenceInfo.text,
          )}
          title="Heuristic model confidence based on data quality and how clearly the 1X2 probabilities favor one outcome. It is not a guarantee."
        >
          Confidence: {confidenceInfo.label}
        </Badge>
        <span className="text-muted-foreground">
          Data Quality: {(prediction.data_quality * 100).toFixed(0)}%
        </span>
      </div>

      {prediction.ai_explanation && (
        <div className="mt-3 rounded-lg bg-muted/50 p-2 text-xs italic">
          &ldquo;{prediction.ai_explanation}&rdquo;
        </div>
      )}
    </div>
  );
}

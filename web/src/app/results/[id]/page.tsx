import Link from "next/link";
import { ArrowLeft, CalendarDays, Trophy } from "lucide-react";
import { api } from "@/lib/api";
import type { PredictionResultDetails } from "@/types/models";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { RetryableError } from "@/components/retryable-error";

interface ResultDetailPageProps {
  params: Promise<{ id: string }>;
}

export const revalidate = 0;

export async function generateMetadata({ params }: ResultDetailPageProps) {
  const { id } = await params;
  try {
    const result = await api.getPredictionResult(id);
    return {
      title: `${result.home_team_name} vs ${result.away_team_name} | Result | Football AI`,
      description: `Final result and match outcome for ${result.home_team_name} vs ${result.away_team_name}.`,
    };
  } catch {
    return { title: `Match result | Football AI` };
  }
}

export default async function ResultDetailPage({
  params,
}: ResultDetailPageProps) {
  const { id } = await params;
  let result: PredictionResultDetails;

  try {
    result = await api.getPredictionResult(id);
  } catch (error) {
    return (
      <div className="px-4 py-6 sm:px-0">
        <RetryableError
          message={error instanceof Error ? error.message : "Could not load match result"}
        />
      </div>
    );
  }

  const predictedWinner = getPredictedWinner(result);
  const overUnderPick =
    result.over_2_5_probability == null
      ? "Not available"
      : result.over_2_5_probability >= 0.5
        ? "Over 2.5 goals"
        : "Under 2.5 goals";
  const bttsPick =
    result.btts_probability == null
      ? "Not available"
      : result.btts_probability >= 0.5
        ? "Both teams to score"
        : "At least one team not to score";

  return (
    <div className="mx-auto max-w-4xl space-y-5 px-4 py-5 sm:px-0 sm:py-6">
      <Link
        href="/results"
        className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="mr-1 h-4 w-4" />
        Back to results
      </Link>

      <Card className="overflow-hidden">
        <CardHeader className="text-center">
          <Badge variant="secondary" className="mx-auto w-fit">
            {result.league_name}
          </Badge>
          <CardTitle className="mt-2 min-w-0 text-balance text-xl sm:text-2xl">
            <span className="[overflow-wrap:anywhere]">{result.home_team_name}</span>{" "}
            <span className="whitespace-nowrap text-muted-foreground">vs</span>{" "}
            <span className="[overflow-wrap:anywhere]">{result.away_team_name}</span>
          </CardTitle>
          <CardDescription>
            {result.match_kickoff ? (
              <>
                <CalendarDays className="mr-1 inline h-3.5 w-3.5" />
                {new Date(result.match_kickoff).toLocaleString()}
              </>
            ) : (
              result.match_status
            )}
          </CardDescription>
        </CardHeader>
        <CardContent className="pb-6 text-center">
          <div className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
            Final score
          </div>
          {result.home_score != null && result.away_score != null ? (
            <div className="mt-1 flex items-center justify-center gap-4 text-4xl font-black tabular-nums sm:text-5xl">
              <span>{result.home_score}</span>
              <span className="text-muted-foreground">–</span>
              <span>{result.away_score}</span>
            </div>
          ) : (
            <p className="mt-2 text-sm text-muted-foreground">Final score is not available yet.</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Trophy className="h-5 w-5 text-primary" />
            Match outcome
          </CardTitle>
          <CardDescription>
            Saved verification for this prediction, refreshed from the current result record.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-3">
          <OutcomeItem
            label="Win prediction"
            pick={predictedWinner}
            verified={result.admin_verify_win}
          />
          <OutcomeItem
            label="Goals"
            pick={overUnderPick}
            verified={result.admin_verify_over_2_5}
          />
          <OutcomeItem
            label="Both teams to score"
            pick={bttsPick}
            verified={result.admin_verify_gg}
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>AI Match Analysis</CardTitle>
          <CardDescription>
            AI-generated context saved with this match prediction.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm leading-6">
            {result.ai_explanation ||
              "AI analysis is not available for this prediction."}
          </p>
        </CardContent>
      </Card>

      {result.evaluated_at && (
        <p className="text-center text-xs text-muted-foreground">
          Outcome last evaluated {new Date(result.evaluated_at).toLocaleString()}
        </p>
      )}
    </div>
  );
}

function OutcomeItem({
  label,
  pick,
  verified,
}: {
  label: string;
  pick: string;
  verified?: boolean | null;
}) {
  const status =
    verified === true
      ? "Correct"
      : verified === false
        ? "Incorrect"
        : "Awaiting verification";

  return (
    <div className="rounded-xl border border-border/80 bg-muted/20 p-4">
      <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <div className="mt-1 font-semibold text-foreground">{pick}</div>
      <div
        className={`mt-3 text-sm font-semibold ${
          verified === true
            ? "text-green-600"
            : verified === false
              ? "text-red-600"
              : "text-muted-foreground"
        }`}
      >
        {status}
      </div>
    </div>
  );
}

function getPredictedWinner(result: PredictionResultDetails): string {
  const probabilities = [
    { name: result.home_team_name, value: result.home_probability },
    { name: "Draw", value: result.draw_probability },
    { name: result.away_team_name, value: result.away_probability },
  ].filter((item): item is { name: string; value: number } => item.value != null);

  if (probabilities.length === 0) return "Not available";
  return probabilities.reduce((best, current) =>
    current.value > best.value ? current : best,
  ).name;
}

import { Suspense } from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { api } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { PredictionSummary } from "@/components/prediction-summary";
import { ProbabilityBars } from "@/components/probability-bars";
import { TopScorelines } from "@/components/top-scorelines";
import { ExpectedGoalsDisplay } from "@/components/expected-goals";
import { MarketsDisplay, OverUnderChart } from "@/components/markets-display";
import { LoadingState } from "@/components/loading-states";
import { RetryableError } from "@/components/retryable-error";
import type { PredictionDetail } from "@/types/models";

interface PredictionDetailPageProps {
  params: Promise<{ id: string }>;
}

export async function generateMetadata({ params }: PredictionDetailPageProps) {
  const { id } = await params;
  try {
    const res = await api.getPredictionById(id);
    let matchHome = "Unknown";
    let matchAway = "Unknown";
    try {
      const match = await api.getMatch(res.match_id);
      matchHome = match.home_team_name || match.home_team?.name || "Unknown";
      matchAway = match.away_team_name || match.away_team?.name || "Unknown";
    } catch {}
    return {
      title: `${matchHome} vs ${matchAway} | Prediction | Football AI`,
      description: `AI-powered prediction for ${matchHome} vs ${matchAway}.`,
    };
  } catch {
    return { title: `Prediction ${id} | Football AI` };
  }
}

export const revalidate = 60;

export default async function PredictionDetailPage({
  params,
}: PredictionDetailPageProps) {
  const { id } = await params;

  return (
    <div className="space-y-6">
      <div>
        <Link
          href="/predictions"
          className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="mr-1 h-4 w-4" />
          Back to predictions
        </Link>
      </div>

      <Suspense fallback={<LoadingState message="Loading prediction..." />}>
        <PredictionDetailContent predictionId={id} />
      </Suspense>
    </div>
  );
}

async function PredictionDetailContent({
  predictionId,
}: {
  predictionId: string;
}) {
  let prediction: PredictionDetail | null = null;
  let error: Error | null = null;

  try {
    const res = await api.getPredictionById(predictionId);
    const match = await api.getMatch(res.match_id);

    const homeName =
      match.home_team_name || match.home_team?.name || "Home Team";
    const awayName =
      match.away_team_name || match.away_team?.name || "Away Team";

    prediction = {
      prediction_id: res.prediction_id,
      match_id: res.match_id,
      match_home_team: homeName,
      match_away_team: awayName,
      model: res.model_version || "poisson",
      model_version: res.model_version || "v1.0.0",
      prediction_version: res.prediction_version || "v1.0.0",
      generated_at: res.generated_at || new Date().toISOString(),
      lambda_home: res.lambda_home || 1.5,
      lambda_away: res.lambda_away || 1.2,
      expected_goals: {
        home: res.lambda_home || 1.5,
        away: res.lambda_away || 1.2,
      },
      expected_total_goals: (res.lambda_home || 1.5) + (res.lambda_away || 1.2),
      result_probabilities: {
        home: res.home_probability || 0,
        draw: res.draw_probability || 0,
        away: res.away_probability || 0,
      },
      top_scoreline: res.top_scorelines?.[0]
        ? {
            home_goals: res.top_scorelines[0].home_goals,
            away_goals: res.top_scorelines[0].away_goals,
            probability: res.top_scorelines[0].probability,
          }
        : null,
      top_4_scorelines: res.top_scorelines.map((sl) => ({
        home_goals: sl.home_goals,
        away_goals: sl.away_goals,
        probability: sl.probability,
      })),
      score_matrix: null,
      goal_distributions: null,
      markets: {
        over_under: {
          over_0_5: 0,
          over_1_5: 0,
          over_2_5: res.over_2_5_probability || 0,
          over_3_5: 0,
          over_4_5: 0,
          under_0_5: 0,
          under_1_5: 0,
          under_2_5: res.under_2_5_probability || 0,
          under_3_5: 0,
          under_4_5: 0,
        },
        btts: {
          yes: res.btts_probability || 0,
          no: 1 - (res.btts_probability || 0),
        },
        clean_sheets: { home_clean_sheet: 0, away_clean_sheet: 0 },
        double_chance: { home_or_draw: 0, draw_or_away: 0, home_or_away: 0 },
      },
      data_quality: 0.5,
      model_confidence: res.confidence || 0.5,
      prediction_stability: "medium",
      feature_explanations: [],
      feature_snapshot: res.feature_snapshot || {},
      model_parameters: {},
      research: {
        available: false,
        data_quality: 0,
        sources_count: 0,
        injuries_count: 0,
        suspensions_count: 0,
        lineups_count: 0,
        team_news_count: 0,
        conflicts_count: 0,
        average_credibility: 0,
        average_freshness: 0,
      },
      ai_adjustment: {
        applied: !!res.ai_adjustment,
        version: null,
        home_attack_adjustment: 0,
        away_attack_adjustment: 0,
        home_defense_adjustment: 0,
        away_defense_adjustment: 0,
        confidence: 0,
        reason_codes: [],
        source_ids: [],
      },
      ai_explanation: res.ai_explanation || null,
      confidence: res.confidence || 0.5,
      uncertainty: 1 - (res.confidence || 0.5),
      source_ids: res.source_ids || [],
    };
  } catch (e) {
    error = e instanceof Error ? e : new Error("Failed to load prediction");
  }

  if (error) {
    return <RetryableError message={error.message} />;
  }

  if (!prediction) return null;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span>Prediction Details</span>
            <Badge variant="secondary" className="text-xs">
              {prediction.model_version}
            </Badge>
          </CardTitle>
          <CardDescription>
            Generated: {new Date(prediction.generated_at).toLocaleString()}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <PredictionSummary prediction={prediction} showMatchInfo={false} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Result Probabilities</CardTitle>
        </CardHeader>
        <CardContent>
          <ProbabilityBars
            home={prediction.result_probabilities.home}
            draw={prediction.result_probabilities.draw}
            away={prediction.result_probabilities.away}
            homeTeam={prediction.match_home_team}
            awayTeam={prediction.match_away_team}
          />
        </CardContent>
      </Card>

      {prediction.top_4_scorelines &&
        prediction.top_4_scorelines.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Top Scoreline Predictions</CardTitle>
            </CardHeader>
            <CardContent>
              <TopScorelines scorelines={prediction.top_4_scorelines} />
            </CardContent>
          </Card>
        )}

      {prediction.expected_goals && (
        <Card>
          <CardHeader>
            <CardTitle>Expected Goals</CardTitle>
          </CardHeader>
          <CardContent>
            <ExpectedGoalsDisplay
              xg={prediction.expected_goals}
              lambdaHome={prediction.lambda_home}
              lambdaAway={prediction.lambda_away}
              homeTeam={prediction.match_home_team}
              awayTeam={prediction.match_away_team}
            />
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Market Probabilities</CardTitle>
        </CardHeader>
        <CardContent>
          <OverUnderChart markets={prediction.markets} />
          <div className="mt-4">
            <MarketsDisplay markets={prediction.markets} />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Feature Snapshot</CardTitle>
        </CardHeader>
        <CardContent>
          <pre className="text-xs overflow-x-auto">
            {JSON.stringify(prediction.feature_snapshot, null, 2)}
          </pre>
        </CardContent>
      </Card>

      {prediction.ai_explanation && (
        <Card>
          <CardHeader>
            <CardTitle>AI Explanation</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm italic leading-relaxed">
              &ldquo;{prediction.ai_explanation}&rdquo;
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

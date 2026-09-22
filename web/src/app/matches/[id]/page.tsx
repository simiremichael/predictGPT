import { Suspense } from "react";
import Image from "next/image";
import { Calendar, Clock, MapPin, Shield, Trophy, AlertCircle, ExternalLink } from "lucide-react";
import { api } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { ProbabilityBars } from "@/components/probability-bars";
import { TopScorelines } from "@/components/top-scorelines";
import { GoalDistributionsView } from "@/components/goal-distributions";
import { ScoreMatrixGrid } from "@/components/score-matrix";
import { ExpectedGoalsDisplay } from "@/components/expected-goals";
import { MarketsDisplay, OverUnderChart } from "@/components/markets-display";
import { PredictionSummary } from "@/components/prediction-summary";
import { LoadingState, ErrorBoundary } from "@/components/loading-states";
import { getMatchStatusColor, getMatchStatusLabel, formatTime, formatDateTime } from "@/lib/formatters";
import { getTeamDisplayName } from "@/lib/predictions";
import type { MatchDetail, PredictionDetail, ResearchData } from "@/types/models";

interface MatchDetailPageProps {
  params: Promise<{ id: string }>;
}

export async function generateMetadata({ params }: MatchDetailPageProps) {
  const { id } = await params;
  try {
    const match = await api.getMatch(id);
    const home = match.home_team?.name || match.home_team_name || "Home Team";
    const away = match.away_team?.name || match.away_team_name || "Away Team";
    return {
      title: `${home} vs ${away} | Football AI`,
      description: `Match prediction and analysis for ${home} vs ${away}.`,
    };
  } catch {
    return { title: `Match ${id} | Football AI` };
  }
}

export const revalidate = 60;

export default async function MatchDetailPage({ params }: MatchDetailPageProps) {
  const { id } = await params;

  return (
    <div className="space-y-6">
      <Suspense
        fallback={<LoadingState message="Loading match details..." />}
      >
        <MatchDetailContent matchId={id} />
      </Suspense>
    </div>
  );
}

async function MatchDetailContent({ matchId }: { matchId: string }) {
  let matchDetail: MatchDetail | null = null;
  let error: Error | null = null;

  try {
    matchDetail = await api.getMatch(matchId);
  } catch (e) {
    error = e instanceof Error ? e : new Error("Failed to load match");
  }

  if (error) {
    return (
      <ErrorBoundary
        error={error}
        reset={() => window.location.reload()}
      />
    );
  }

  if (!matchDetail) return <LoadingState message="Loading match..." />;

  return (
    <div className="space-y-6">
      <MatchHeader match={matchDetail} />
      <PredictionSection matchId={matchId} />
      <Suspense
        fallback={<LoadingState message="Loading match statistics..." />}
      >
        <MatchStatsSection stats={matchDetail.statistics} />
      </Suspense>
      <Suspense
        fallback={<LoadingState message="Loading team form..." />}
      >
        <TeamFormSection match={matchDetail} />
      </Suspense>
      <Suspense
        fallback={<LoadingState message="Loading head-to-head..." />}
      >
        <HeadToHeadSection h2h={matchDetail.h2h} />
      </Suspense>
      <Suspense
        fallback={<LoadingState message="Loading injuries..." />}
      >
        <InjuriesSection injuries={matchDetail.injuries} />
      </Suspense>
      <Suspense
        fallback={<LoadingState message="Loading suspensions..." />}
      >
        <SuspensionsSection suspensions={matchDetail.suspensions} />
      </Suspense>
      <Suspense
        fallback={<LoadingState message="Loading lineups..." />}
      >
        <LineupsSection lineups={matchDetail.lineups} />
      </Suspense>
      <Suspense
        fallback={<LoadingState message="Loading odds..." />}
      >
        <OddsSection odds={matchDetail.odds} />
      </Suspense>
    </div>
  );
}

function MatchHeader({ match }: { match: MatchDetail }) {
  const home = match.home_team;
  const away = match.away_team;
  const homeName = home?.name || match.home_team_name || "Home Team";
  const awayName = away?.name || match.away_team_name || "Away Team";
  const kickoffAt = match.kickoff_at ? new Date(match.kickoff_at) : null;

  return (
    <Card className="overflow-hidden">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Badge variant="secondary" className="text-xs">
              {match.league?.name || match.league_name}
            </Badge>
            <Badge className={getMatchStatusColor(match.status)}>
              {getMatchStatusLabel(match.status)}
            </Badge>
          </div>
          {kickoffAt && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Calendar className="h-4 w-4" />
              {formatDateTime(kickoffAt)}
              <Clock className="h-4 w-4" />
              {formatTime(kickoffAt)}
            </div>
          )}
        </div>
      </CardHeader>

      <CardContent>
        <div className="flex items-center justify-between py-4">
          <div className="flex flex-1 flex-col items-center">
            {home?.logo_url ? (
              <Image
                src={home.logo_url}
                alt={homeName}
                width={48}
                height={48}
                className="object-contain"
              />
            ) : (
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-muted text-xl font-bold">
                {getTeamDisplayName(homeName)?.charAt(0)}
              </div>
            )}
            <span className="mt-2 text-lg font-semibold">{homeName}</span>
            {home?.venue_city && (
              <span className="text-xs text-muted-foreground">
                {home.venue_city}
              </span>
            )}
          </div>

          <div className="flex items-center">
            {match.is_finished ? (
              <div className="flex items-center gap-4 text-2xl font-bold">
                {match.home_score} - {match.away_score}
              </div>
            ) : (
              <div className="text-sm font-bold text-muted-foreground">
                VS
              </div>
            )}
          </div>

          <div className="flex flex-1 flex-col items-center">
            {away?.logo_url ? (
              <Image
                src={away.logo_url}
                alt={awayName}
                width={48}
                height={48}
                className="object-contain"
              />
            ) : (
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-muted text-xl font-bold">
                {getTeamDisplayName(awayName)?.charAt(0)}
              </div>
            )}
            <span className="mt-2 text-lg font-semibold">{awayName}</span>
            {away?.venue_city && (
              <span className="text-xs text-muted-foreground">
                {away.venue_city}
              </span>
            )}
          </div>
        </div>

        {match.venue && (
          <div className="border-t border-border pt-3 text-center text-sm text-muted-foreground">
            <MapPin className="mb-1 h-4 w-4 inline-block" />
            {match.venue}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

async function PredictionSection({ matchId }: { matchId: string }) {
  let prediction: PredictionDetail | null = null;
  let error: Error | null = null;

  try {
    const predictionData = await api.getPrediction(matchId);
    prediction = predictionData.data;
  } catch (e) {
    error = e instanceof Error ? e : new Error("Failed to load prediction");
  }

  if (error) {
    return (
      <ErrorBoundary
        error={error}
        reset={() => window.location.reload()}
      />
    );
  }

  if (!prediction) {
    return (
        <Card>
          <CardHeader>
            <CardTitle>AI Prediction</CardTitle>
            <CardDescription>No prediction available for this match.</CardDescription>
          </CardHeader>
        </Card>
      );
    }

    return (
      <div className="space-y-4">
        <PredictionSummary prediction={prediction} />

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

        {prediction.top_4_scorelines && prediction.top_4_scorelines.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Top 4 Scoreline Predictions</CardTitle>
            </CardHeader>
            <CardContent>
              <TopScorelines scorelines={prediction.top_4_scorelines} />
            </CardContent>
          </Card>
        )}

        {prediction.score_matrix && (
          <Card>
            <CardHeader>
              <CardTitle>Score Probability Matrix</CardTitle>
              <CardDescription>
                Probability of each exact scoreline
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ScoreMatrixGrid
                matrix={prediction.score_matrix}
                homeTeam={prediction.match_home_team}
                awayTeam={prediction.match_away_team}
                highlightTop4={prediction.top_4_scorelines}
              />
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

        {prediction.goal_distributions && (
          <Card>
            <CardHeader>
              <CardTitle>Goal Distributions</CardTitle>
            </CardHeader>
            <CardContent>
              <GoalDistributionsView
                distributions={prediction.goal_distributions}
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

        {prediction.ai_explanation && (
          <Card>
            <CardHeader>
              <CardTitle>AI Explanation</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm italic">{prediction.ai_explanation}</p>
            </CardContent>
          </Card>
        )}

        {prediction.ai_adjustment && prediction.ai_adjustment.applied && (
          <Card>
            <CardHeader>
              <CardTitle>Research Adjustment Applied</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 text-sm">
                <p>
                  Home attack:{" "}
                  {prediction.ai_adjustment.home_attack_adjustment > 0 ? "+" : ""}
                  {prediction.ai_adjustment.home_attack_adjustment.toFixed(3)}
                </p>
                <p>
                  Away attack:{" "}
                  {prediction.ai_adjustment.away_attack_adjustment > 0 ? "+" : ""}
                  {prediction.ai_adjustment.away_attack_adjustment.toFixed(3)}
                </p>
                {prediction.ai_adjustment.reason_codes.length > 0 && (
                  <div className="mt-2">
                    <span className="font-medium">Reasons: </span>
                    {prediction.ai_adjustment.reason_codes.map((code, i) => (
                      <Badge key={i} variant="outline" className="ml-1 text-xs">
                        {code}
                      </Badge>
                    ))}
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        )}

        {prediction.research && prediction.research.available && (
          <ResearchSection matchId={matchId} />
        )}
      </div>
    );
}

async function ResearchSection({ matchId }: { matchId: string }) {
  let research: ResearchData | null = null;

  try {
    research = await api.getResearch(matchId);
  } catch {
    return null;
  }

  if (!research) return null;

  return (
      <Card>
        <CardHeader>
          <CardTitle>Research & Analysis</CardTitle>
          <CardDescription>
            Web-sourced data: {research.sources.length} sources,{" "}
            {research.injuries.length} injuries,{" "}
            {research.suspensions.length} suspensions
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {research.sources.length > 0 && (
              <div>
                <h4 className="text-sm font-semibold mb-2">Sources</h4>
                <div className="space-y-2">
                  {research.sources.slice(0, 5).map((source, i) => (
                    <div key={i} className="flex items-start gap-2">
                      <AlertCircle className="h-4 w-4 text-muted-foreground mt-0.5" />
                      <div className="flex-1">
                        <a
                          href={source.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-sm font-medium hover:underline flex items-center gap-1"
                        >
                          {source.title || source.url}
                          <ExternalLink className="h-3 w-3" />
                        </a>
                        {source.publisher && (
                          <p className="text-xs text-muted-foreground">
                            {source.publisher}
                          </p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {research.injuries.length > 0 && (
              <div>
                <h4 className="text-sm font-semibold mb-2">Injuries</h4>
                {research.injuries.map((injury, i) => (
                  <div key={i} className="text-sm border-l-2 border-warning pl-2">
                    <span className="font-medium">{injury.subject}</span> -{" "}
                    {injury.claim}
                  </div>
                ))}
              </div>
            )}
            {research.team_news.length > 0 && (
              <div>
                <h4 className="text-sm font-semibold mb-2">Team News</h4>
                {research.team_news.map((news, i) => (
                  <div key={i} className="text-sm border-l-2 border-primary pl-2">
                    <span className="font-medium">{news.subject}</span> -{" "}
                    {news.claim}
                  </div>
                ))}
              </div>
            )}
          </div>
          <div className="mt-4 border-t border-border pt-3 text-center">
            <Badge variant="outline" className="text-xs">
              Data Quality: {(research.data_quality * 100).toFixed(1)}%
            </Badge>
          </div>
        </CardContent>
      </Card>
    );
}

function MatchStatsSection({
  stats,
}: {
  stats?: Record<string, unknown> | null;
}) {
  if (!stats) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Match Statistics</CardTitle>
      </CardHeader>
      <CardContent>
        <pre className="text-xs overflow-x-auto">
          {JSON.stringify(stats, null, 2)}
        </pre>
      </CardContent>
    </Card>
  );
}

function TeamFormSection({ match }: { match: MatchDetail }) {
  const form = match.form;
  if (!form) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Team Form</CardTitle>
      </CardHeader>
      <CardContent>
        <pre className="text-xs overflow-x-auto">
          {JSON.stringify(form, null, 2)}
        </pre>
      </CardContent>
    </Card>
  );
}

function HeadToHeadSection({ h2h }: { h2h?: Record<string, unknown> | null }) {
  if (!h2h) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Head to Head</CardTitle>
      </CardHeader>
      <CardContent>
        <pre className="text-xs overflow-x-auto">
          {JSON.stringify(h2h, null, 2)}
        </pre>
      </CardContent>
    </Card>
  );
}

function InjuriesSection({
  injuries,
}: {
  injuries: Array<Record<string, unknown>>;
}) {
  if (!injuries.length) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <Shield className="inline h-5 w-5 mr-2" />
          Injuries
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-2">
          {injuries.map((injury, i) => (
            <div key={i} className="border-b border-border py-2 last:border-0">
              <span className="font-medium">{String(injury.player_name || "Unknown")}</span>
              <span className="text-xs text-muted-foreground ml-2">
                {String(injury.position || "")} - {String(injury.injury_type || "")}
              </span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function SuspensionsSection({
  suspensions,
}: {
  suspensions: Array<Record<string, unknown>>;
}) {
  if (!suspensions.length) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <Trophy className="inline h-5 w-5 mr-2" />
          Suspensions
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-2">
          {suspensions.map((susp, i) => (
            <div key={i} className="border-b border-border py-2 last:border-0">
              <span className="font-medium">{String(susp.player_name || "Unknown")}</span>
              <span className="text-xs text-muted-foreground ml-2">
                {String(susp.reason || "")} - {String(susp.suspension_type || "")}
              </span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function LineupsSection({
  lineups,
}: {
  lineups: Array<Record<string, unknown>>;
}) {
  if (!lineups.length) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Confirmed Lineups</CardTitle>
      </CardHeader>
      <CardContent>
        <pre className="text-xs overflow-x-auto">
          {JSON.stringify(lineups, null, 2)}
        </pre>
      </CardContent>
    </Card>
  );
}

function OddsSection({
  odds,
}: {
  odds?: Record<string, unknown> | null;
}) {
  if (!odds) return null;

  const markets = odds.markets as Array<Record<string, unknown>> | undefined;
  if (!markets || markets.length === 0) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Latest Odds</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {markets.slice(0, 4).map((market, i) => (
            <div key={i} className="border-b border-border py-2 last:border-0">
              <span className="font-medium">{String(market.name || market.key || "Market")}</span>
              <div className="mt-1 flex gap-3 text-sm">
                {Array.isArray(market.bookmakers) &&
                  market.bookmakers.slice(0, 3).map((bm: Record<string, unknown>, j) => (
                    <span key={j} className="text-muted-foreground">
                      {String(bm.name || bm.key || "Bookmaker")}
                    </span>
                  ))}
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

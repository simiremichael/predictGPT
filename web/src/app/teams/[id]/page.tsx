import { Suspense } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { LoadingState, EmptyState } from "@/components/loading-states";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { MatchCard } from "@/components/match-card";
import type { MatchBrief } from "@/types/models";
import Image from "next/image";

interface TeamDetailPageProps {
  params: Promise<{ id: string }>;
}

export async function generateMetadata({ params }: TeamDetailPageProps) {
  const { id } = await params;
  try {
    const team = await api.getTeam(id);
    return {
      title: `${team.name} | Football AI`,
      description: `Team page for ${team.name}.`,
    };
  } catch {
    return { title: `Team ${id} | Football AI` };
  }
}

export const revalidate = 60;

export default async function TeamPage({ params }: TeamDetailPageProps) {
  const { id } = await params;

  const team = await api.getTeam(id);
  const teamMatches = await api.getTeamMatches(id, { page_size: 20 });
  const teamStats = await api.getTeamStats(id);

  return (
    <div className="space-y-6">
      <section className="surface-card rounded-[1.75rem] p-5 sm:p-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <Link
              href="/teams"
              className="text-sm text-muted-foreground hover:text-foreground"
            >
              Teams
            </Link>
            <span className="text-sm text-muted-foreground">/</span>
            <h1 className="text-3xl font-black tracking-[-0.06em] text-foreground">
              {team.name}
            </h1>
          </div>
          {team.is_active !== false && (
            <Badge
              variant="default"
              className="w-fit rounded-full px-3 py-1.5 text-xs font-semibold"
            >
              Active
            </Badge>
          )}
        </div>

        <div className="mt-5 flex items-start gap-5">
          {team.logo_url ? (
            <Image
              src={team.logo_url}
              alt={team.name}
              width={64}
              height={64}
              className="h-16 w-16 rounded-2xl object-contain ring-1 ring-border bg-background/60 p-2"
            />
          ) : (
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-primary/12 to-cyan-500/10 text-2xl font-black text-primary ring-1 ring-primary/10">
              {team.short_name?.charAt(0) || team.name.charAt(0)}
            </div>
          )}

          <div className="space-y-1">
            <p className="text-sm text-muted-foreground">{team.country}</p>
            {team.venue_name && (
              <p className="text-sm text-foreground">
                <span className="font-semibold">Venue:</span> {team.venue_name}
                {team.venue_city && `, ${team.venue_city}`}
              </p>
            )}
          </div>
        </div>
      </section>

      <Card className="surface-card rounded-[1.5rem]">
        <CardHeader>
          <CardTitle className="text-xl font-black tracking-[-0.04em] text-foreground">
            Team Statistics
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {teamStats.statistics?.map(
              (
                stat: {
                  league_id?: number;
                  season_id?: number;
                  games_played?: number;
                  wins?: number;
                  draws?: number;
                  losses?: number;
                  goals_for?: number;
                  goals_against?: number;
                  points?: number;
                  position?: number | string;
                  average_xg?: number;
                  average_xga?: number;
                },
                idx: number,
              ) => (
                <div
                  key={idx}
                  className="rounded-2xl border border-border bg-background/60 p-3"
                >
                  <div className="text-sm font-semibold text-foreground">
                    {stat.league_id
                      ? `League ${stat.league_id}`
                      : `Season ${stat.season_id}`}
                  </div>
                  <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-muted-foreground">
                    <div>P: {stat.games_played ?? 0}</div>
                    <div>W: {stat.wins ?? 0}</div>
                    <div>D: {stat.draws ?? 0}</div>
                    <div>L: {stat.losses ?? 0}</div>
                    <div>GF: {stat.goals_for ?? 0}</div>
                    <div>GA: {stat.goals_against ?? 0}</div>
                    <div>Pts: {stat.points ?? 0}</div>
                    <div>Pos: {stat.position ?? "N/A"}</div>
                    <div>xG: {stat.average_xg?.toFixed(2) ?? "N/A"}</div>
                    <div>xGA: {stat.average_xga?.toFixed(2) ?? "N/A"}</div>
                  </div>
                </div>
              ),
            ) || []}
          </div>
        </CardContent>
      </Card>

      <Card className="surface-card rounded-[1.5rem]">
        <CardHeader>
          <CardTitle className="text-xl font-black tracking-[-0.04em] text-foreground">
            Recent Matches
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Suspense fallback={<LoadingState message="Loading matches..." />}>
            <TeamMatches matches={teamMatches.data} />
          </Suspense>
        </CardContent>
      </Card>
    </div>
  );
}

function TeamMatches({ matches }: { matches: MatchBrief[] }) {
  if (matches.length === 0) {
    return (
      <EmptyState
        title="No matches"
        description="No match history for this team."
        className="py-4"
      />
    );
  }
  return (
    <div className="space-y-2">
      {matches.map((match) => (
        <MatchCard key={match.id} match={match} showPrediction={false} />
      ))}
    </div>
  );
}

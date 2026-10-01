import { Suspense } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { LoadingState, EmptyState } from "@/components/loading-states";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { MatchCard } from "@/components/match-card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { MatchBrief, TeamSeason, TeamCountry } from "@/types/models";
import Image from "next/image";
import { notFound } from "next/navigation";

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

  const team = await api.getTeam(id).catch(() => null);
  if (!team?.id) {
    notFound();
  }

  const [teamMatches, teamStats, teamSeasons, teamCountries] = await Promise.all([
    api.getTeamMatches(id, { page_size: 20 }).catch(() => null),
    api.getTeamStats(id).catch(() => null),
    api.getTeamSeasons(id).catch(() => null),
    api.getTeamCountries(id).catch(() => null),
  ]);

  const matches = teamMatches?.data ?? [];
  const stats = teamStats?.statistics ?? [];
  const seasons = teamSeasons?.data ?? [];
  const countries = teamCountries?.data ?? [];

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
            {team.short_name && (
              <p className="text-sm text-muted-foreground">
                <span className="font-semibold">Short name:</span> {team.short_name}
              </p>
            )}
          </div>
        </div>
      </section>

      <Tabs defaultValue="info" className="space-y-4">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="info">Info</TabsTrigger>
          <TabsTrigger value="statistics">Statistics</TabsTrigger>
          <TabsTrigger value="seasons">Seasons ({seasons.length || 0})</TabsTrigger>
          <TabsTrigger value="countries">Countries ({countries.length || 0})</TabsTrigger>
        </TabsList>

        <TabsContent value="info">
          <Card className="surface-card rounded-[1.5rem]">
            <CardHeader>
              <CardTitle className="text-xl font-black tracking-[-0.04em] text-foreground">
                Team Information
              </CardTitle>
              <CardDescription>Basic team details and venue information</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                <div className="rounded-2xl border border-border bg-background/60 p-4">
                  <h3 className="text-sm font-semibold text-muted-foreground">Name</h3>
                  <p className="mt-1 text-lg font-medium text-foreground">{team.name}</p>
                </div>
                <div className="rounded-2xl border border-border bg-background/60 p-4">
                  <h3 className="text-sm font-semibold text-muted-foreground">Short Name</h3>
                  <p className="mt-1 text-lg font-medium text-foreground">{team.short_name || "N/A"}</p>
                </div>
                <div className="rounded-2xl border border-border bg-background/60 p-4">
                  <h3 className="text-sm font-semibold text-muted-foreground">Country</h3>
                  <p className="mt-1 text-lg font-medium text-foreground">{team.country || "N/A"}</p>
                </div>
                <div className="rounded-2xl border border-border bg-background/60 p-4">
                  <h3 className="text-sm font-semibold text-muted-foreground">Venue</h3>
                  <p className="mt-1 text-lg font-medium text-foreground">
                    {team.venue_name || "N/A"}
                    {team.venue_city && `, ${team.venue_city}`}
                  </p>
                </div>
                <div className="rounded-2xl border border-border bg-background/60 p-4">
                  <h3 className="text-sm font-semibold text-muted-foreground">Status</h3>
                  <p className="mt-1 text-lg font-medium text-foreground">
                    <Badge variant={team.is_active ? "default" : "secondary"}>
                      {team.is_active ? "Active" : "Inactive"}
                    </Badge>
                  </p>
                </div>
                <div className="rounded-2xl border border-border bg-background/60 p-4">
                  <h3 className="text-sm font-semibold text-muted-foreground">Team ID</h3>
                  <p className="mt-1 text-sm font-mono text-muted-foreground">{team.id}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="statistics">
          <Card className="surface-card rounded-[1.5rem]">
            <CardHeader>
              <CardTitle className="text-xl font-black tracking-[-0.04em] text-foreground">
                Team Statistics
              </CardTitle>
              <CardDescription>Performance statistics across leagues and seasons</CardDescription>
            </CardHeader>
            <CardContent>
              {stats.length > 0 ? (
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  {stats.map(
                    (
                      stat: {
                        league_id?: string | number;
                        season_id?: string | number;
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
                        className="rounded-2xl border border-border bg-background/60 p-4"
                      >
                        <div className="text-sm font-semibold text-foreground mb-2">
                          {stat.league_id
                            ? `League ${stat.league_id}`
                            : `Season ${stat.season_id}`}
                        </div>
                        <div className="grid grid-cols-3 gap-2 text-xs text-muted-foreground">
                          <div>P: <span className="text-foreground font-medium">{stat.games_played ?? 0}</span></div>
                          <div>W: <span className="text-foreground font-medium">{stat.wins ?? 0}</span></div>
                          <div>D: <span className="text-foreground font-medium">{stat.draws ?? 0}</span></div>
                          <div>L: <span className="text-foreground font-medium">{stat.losses ?? 0}</span></div>
                          <div>GF: <span className="text-foreground font-medium">{stat.goals_for ?? 0}</span></div>
                          <div>GA: <span className="text-foreground font-medium">{stat.goals_against ?? 0}</span></div>
                          <div>Pts: <span className="text-foreground font-medium">{stat.points ?? 0}</span></div>
                          <div>Pos: <span className="text-foreground font-medium">{stat.position ?? "N/A"}</span></div>
                          <div>xG: <span className="text-foreground font-medium">{stat.average_xg?.toFixed(2) ?? "N/A"}</span></div>
                          <div>xGA: <span className="text-foreground font-medium">{stat.average_xga?.toFixed(2) ?? "N/A"}</span></div>
                        </div>
                      </div>
                    ),
                  )}
                </div>
              ) : (
                <EmptyState title="No statistics" description="Statistics data not yet available for this team." />
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="seasons">
          <Card className="surface-card rounded-[1.5rem]">
            <CardHeader>
              <CardTitle className="text-xl font-black tracking-[-0.04em] text-foreground">
                Seasons
              </CardTitle>
              <CardDescription>Seasons this team has participated in</CardDescription>
            </CardHeader>
            <CardContent>
              {seasons.length > 0 ? (
                <div className="space-y-3">
                  {seasons.map((season: TeamSeason, idx: number) => (
                    <div
                      key={idx}
                      className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 p-3 rounded-xl border border-border bg-background/60"
                    >
                      <div className="flex items-center gap-3">
                        <Badge
                          variant={season.is_current ? "default" : "outline"}
                          className="text-sm"
                        >
                          {season.year || season.name}
                        </Badge>
                        <div>
                          <p className="font-medium text-foreground">{season.league_name}</p>
                          <p className="text-sm text-muted-foreground">
                            {season.start_date ? new Date(season.start_date).getFullYear() : ""}
                            {season.end_date && season.start_date ? " - " : ""}
                            {season.end_date ? new Date(season.end_date).getFullYear() : ""}
                          </p>
                        </div>
                      </div>
                      <div className="text-sm text-muted-foreground">
                        {season.is_current && <span className="text-primary font-medium">Current</span>}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState title="No seasons" description="Season data not yet available for this team." />
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="countries">
          <Card className="surface-card rounded-[1.5rem]">
            <CardHeader>
              <CardTitle className="text-xl font-black tracking-[-0.04em] text-foreground">
                Countries
              </CardTitle>
              <CardDescription>Countries where this team has played (via league participation)</CardDescription>
            </CardHeader>
            <CardContent>
              {countries.length > 0 ? (
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {countries.map((country: TeamCountry, idx: number) => (
                    <div
                      key={idx}
                      className="rounded-2xl border border-border bg-background/60 p-4 text-center"
                    >
                      <p className="text-2xl font-black text-foreground">{country.league_count}</p>
                      <p className="text-sm text-muted-foreground mt-1">{country.country}</p>
                      <p className="text-xs text-muted-foreground mt-0.5">leagues</p>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState title="No countries" description="Country data not yet available for this team." />
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <Card className="surface-card rounded-[1.5rem]">
        <CardHeader>
          <CardTitle className="text-xl font-black tracking-[-0.04em] text-foreground">
            Recent Matches
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Suspense fallback={<LoadingState message="Loading matches..." />}>
            <TeamMatches matches={matches} />
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

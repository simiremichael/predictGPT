import { Suspense } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { LoadingState, EmptyState } from "@/components/loading-states";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { MatchCard } from "@/components/match-card";
import type { Standing, Season } from "@/types/models";

interface LeagueDetailPageProps {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ page?: string; page_size?: string }>;
}

export async function generateMetadata({ params }: LeagueDetailPageProps) {
  const { id } = await params;
  try {
    const league = await api.getLeague(id);
    return {
      title: `${league.name} | Football AI`,
      description: `League table and matches for ${league.name}.`,
    };
  } catch {
    return { title: `League ${id} | Football AI` };
  }
}

export const revalidate = 60;

export default async function LeaguePage({
  params,
  searchParams,
}: LeagueDetailPageProps) {
  const { id } = await params;
  const sp = await searchParams;
  const standingsPage = parseInt(sp.page || "1", 10);
  const standingsPageSize = parseInt(sp.page_size || "50", 10);

  let league;
  let seasons = { data: [] as Season[], meta: { total: 0 } };
  let standings = { data: [] as Standing[], meta: { total: 0 } };

  try {
    league = await api.getLeague(id);
    seasons = await api.getLeagueSeasons(id, { page_size: 20 });
    standings = await api.getLeagueStandings(id, {
      page: standingsPage,
      page_size: standingsPageSize,
    });
  } catch (error) {
    return (
      <EmptyState
        title="League unavailable"
        description={
          error instanceof Error
            ? error.message
            : "The league data could not be loaded right now."
        }
        className="py-10"
      />
    );
  }

  return (
    <div className="space-y-6">
      <section className="surface-card rounded-[1.75rem] p-5 sm:p-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Link href="/leagues" className="hover:text-foreground">
                Leagues
              </Link>
              <span>/</span>
              <span>{league.name}</span>
            </div>
            <h1 className="mt-2 text-3xl font-black tracking-[-0.06em] text-foreground">
              {league.name}
            </h1>
            {league.country && (
              <p className="mt-2 text-sm text-muted-foreground">
                {league.country}
              </p>
            )}
          </div>

          <Badge
            variant={league.is_active ? "default" : "secondary"}
            className="w-fit rounded-full px-3 py-1.5 text-xs font-semibold"
          >
            {league.is_active ? "Active" : "Inactive"}
          </Badge>
        </div>
      </section>

      {league.current_season && (
        <Card className="surface-card rounded-[1.5rem]">
          <CardHeader>
            <CardTitle className="text-sm font-medium uppercase tracking-[0.12em] text-muted-foreground">
              Current Season
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-lg font-semibold text-foreground">
              {String(
                league.current_season?.name ||
                  league.current_season?.year ||
                  "N/A",
              )}
            </p>
          </CardContent>
        </Card>
      )}

      {standings.data.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>Standings</CardTitle>
            <CardDescription>
              {standings.meta.total} teams in the table
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border">
                    <th className="text-left py-2">#</th>
                    <th className="text-left py-2">Team</th>
                    <th className="text-center py-2">P</th>
                    <th className="text-center py-2">W</th>
                    <th className="text-center py-2">D</th>
                    <th className="text-center py-2">L</th>
                    <th className="text-center py-2">GF</th>
                    <th className="text-center py-2">GA</th>
                    <th className="text-center py-2">GD</th>
                    <th className="text-center py-2">Pts</th>
                  </tr>
                </thead>
                <tbody>
                  {standings.data.map((standing: Standing, idx: number) => (
                    <tr
                      key={standing.team_id || idx}
                      className="border-b border-border/50"
                    >
                      <td className="py-2 font-medium">{standing.position}</td>
                      <td className="py-2">{standing.team_name}</td>
                      <td className="text-center py-2">{standing.played}</td>
                      <td className="text-center py-2">{standing.wins}</td>
                      <td className="text-center py-2">{standing.draws}</td>
                      <td className="text-center py-2">{standing.losses}</td>
                      <td className="text-center py-2">{standing.goals_for}</td>
                      <td className="text-center py-2">
                        {standing.goals_against}
                      </td>
                      <td className="text-center py-2">
                        {standing.goal_difference}
                      </td>
                      <td className="text-center py-2 font-semibold">
                        {standing.points}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      ) : (
        <EmptyState
          title="No standings"
          description="Standings data not yet available for this league."
        />
      )}

      <Card>
        <CardHeader>
          <CardTitle>Upcoming Matches</CardTitle>
        </CardHeader>
        <CardContent>
          <Suspense fallback={<LoadingState message="Loading matches..." />}>
            <LeagueMatches leagueId={id} />
          </Suspense>
        </CardContent>
      </Card>

      {seasons.data.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Seasons</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {seasons.data.map((season: Season) => (
                <Badge
                  key={season.id}
                  variant={season.is_current ? "default" : "outline"}
                  className="text-xs"
                >
                  {season.year || season.name}
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

async function LeagueMatches({ leagueId }: { leagueId: string }) {
  let result;
  let error = false;

  try {
    result = await api.listMatches({
      league_id: leagueId,
      upcoming: true,
      page_size: 10,
    });
  } catch {
    error = true;
  }

  if (error) {
    return (
      <EmptyState
        title="Failed to load matches"
        description="Please try again later."
        className="py-4"
      />
    );
  }

  if (!result) return <LoadingState message="Loading matches..." />;

  if (result.data.length === 0) {
    return (
      <EmptyState
        title="No upcoming matches"
        description="No fixtures scheduled."
        className="py-4"
      />
    );
  }
  return (
    <div className="space-y-2">
      {result.data.map((match) => (
        <MatchCard key={match.id} match={match} showPrediction={false} />
      ))}
    </div>
  );
}

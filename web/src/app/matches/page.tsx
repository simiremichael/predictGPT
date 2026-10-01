import { Calendar } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { MatchesList } from "@/components/matches/matches-list";
import { LoadingState } from "@/components/loading-states";

interface MatchesPageProps {
  searchParams: Promise<{
    today?: string;
    upcoming?: string;
    league_id?: string;
    team_id?: string;
    status?: string;
    date?: string;
    page?: string;
    page_size?: string;
  }>;
}

export const metadata = {
  title: "Matches | Football AI",
  description: "Browse football matches and predictions.",
};

export default async function MatchesPage({ searchParams }: MatchesPageProps) {
  const params = await searchParams;
  const page = parseInt(params.page || "1", 10);
  const pageSize = parseInt(params.page_size || "20", 10);
  const isToday = params.today === "true";
  const isUpcoming = params.upcoming === "true";
  const leagueId = params.league_id || "";
  const teamId = params.team_id || "";
  const status = params.status || "";
  const date = params.date || "";

  return (
    <div className="space-y-6">
      <section className="surface-card rounded-[1.75rem] p-5 sm:p-6">
        <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="section-kicker mb-2">Fixtures</p>
            <h1 className="text-3xl font-black tracking-[-0.06em] text-foreground">
              {isToday
                ? "Today's Matches"
                : isUpcoming
                  ? "Upcoming Matches"
                  : "All Matches"}
            </h1>
            <p className="mt-2 text-sm text-muted-foreground">
              {isToday
                ? "Matches scheduled for today"
                : isUpcoming
                  ? "Upcoming fixtures in the next 7 days"
                  : "All football matches"}
            </p>
          </div>

          <div className="flex items-center gap-2">
            <Badge
              variant="outline"
              className="rounded-full border-primary/20 bg-primary/5 px-3 py-1.5 text-xs font-semibold text-primary"
            >
              <Calendar className="mr-1 h-3 w-3" />
              {new Date().toLocaleDateString()}
            </Badge>
          </div>
        </div>
      </section>

      <MatchesList
        initialPage={page}
        initialPageSize={pageSize}
        initialLeagueId={leagueId}
        initialTeamId={teamId}
        initialStatus={status}
        initialDate={date}
        today={isToday}
        upcoming={isUpcoming}
      />
    </div>
  );
}
import { Calendar } from "lucide-react";
import { api } from "@/lib/api";
import { MatchCard } from "@/components/match-card";
import {
  LoadingState,
  EmptyState,
  PaginationControls,
} from "@/components/loading-states";
import { Badge } from "@/components/ui/badge";
import type { MatchBrief } from "@/types/models";

export const revalidate = 60;

export const metadata = {
  title: "Matches | Football AI",
  description: "Browse football matches and predictions.",
};

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

export default async function MatchesPage({ searchParams }: MatchesPageProps) {
  const params = await searchParams;
  const page = parseInt(params.page || "1", 10);
  const page_size = parseInt(params.page_size || "20", 10);
  const isToday = params.today === "true";
  const isUpcoming = params.upcoming === "true";

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
        page={page}
        pageSize={page_size}
        league_id={params.league_id}
        team_id={params.team_id}
        status={params.status}
        today={isToday}
        upcoming={isUpcoming}
      />
    </div>
  );
}

async function MatchesList({
  page,
  pageSize,
  league_id,
  team_id,
  status,
  today,
  upcoming,
}: {
  page: number;
  pageSize: number;
  league_id?: string;
  team_id?: string;
  status?: string;
  today: boolean;
  upcoming: boolean;
}) {
  let result;
  let error: Error | null = null;

  try {
    if (today) {
      result = await api.getTodayMatches({ page, page_size: pageSize });
    } else if (upcoming) {
      result = await api.getUpcomingMatches({
        days: 7,
        league_id,
        team_id,
        page,
        page_size: pageSize,
      });
    } else {
      result = await api.listMatches({
        league_id,
        team_id,
        status,
        page,
        page_size: pageSize,
      });
    }
  } catch (e) {
    error = e instanceof Error ? e : new Error("Failed to load matches");
  }

  if (error) {
    return (
      <EmptyState title="Unable to load matches" description={error.message} />
    );
  }

  if (!result) return <LoadingState message="Loading matches..." />;

  if (result.data.length === 0) {
    return (
      <EmptyState
        title="No matches found"
        description="Try adjusting your filters or check back later."
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="space-y-3">
        {result.data.map((match: MatchBrief) => (
          <MatchCard
            key={match.id}
            match={match}
            showPrediction={false}
            variant="compact"
          />
        ))}
      </div>
      <PaginationControls
        currentPage={page}
        totalPages={result.meta.total_pages || 1}
        onPageChange={(newPage) => {
          const url = new URL(window.location.href);
          url.searchParams.set("page", String(newPage));
          window.history.pushState({}, "", url.toString());
        }}
      />
    </div>
  );
}

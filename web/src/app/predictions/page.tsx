import { History, Shield } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { PredictionsList } from "@/components/predictions/predictions-list";
import { PredictionGuaranteeBadge } from "@/components/prediction-guarantee-badge";
import { fetchCachedPredictions } from "@/lib/cached-api";

interface PredictionsPageProps {
  searchParams: Promise<{
    match_id?: string;
    league_id?: string;
    team_id?: string;
  }>;
}

export const revalidate = 0;

export const metadata = {
  title: "Predictions | Football AI",
  description: "Browse predictions for unfinished football matches.",
};

export default async function PredictionsPage({
  searchParams,
}: PredictionsPageProps) {
  const params = await searchParams;

  let initialData: Awaited<ReturnType<typeof fetchCachedPredictions>> | null = null;
  try {
    initialData = await fetchCachedPredictions({
      match_id: params.match_id,
      league_id: params.league_id,
      team_id: params.team_id,
      played: false,
      max_elapsed_minutes: 100,
      page: 1,
      page_size: 50,
    });
  } catch {
    initialData = null;
  }

  return (
    <div className="space-y-6">
      <section className="surface-card rounded-[1.75rem] p-5 sm:p-6">
        <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="section-kicker mb-2">Insights</p>
            <h1 className="text-3xl font-black tracking-[-0.06em] text-foreground">
              Predictions
            </h1>
            <p className="mt-2 text-sm text-muted-foreground">
              Upcoming matches and unfinished matches within 100 minutes of kickoff
            </p>
               <div
              role="note"
              className="mt-4 rounded-xl border border-primary/20 bg-primary/5 px-4 py-3 text-sm leading-6 text-muted-foreground"
            >
              <span className="font-semibold text-foreground">Accumulator tip:</span>{" "}
              Keep your slip to a few games. Adding more selections usually lowers
              the chance of every pick being correct. You can also compare the
              same match across 1X2, goals, and BTTS markets instead of adding
              more games.
            </div>

            <PredictionGuaranteeBadge />
          </div>

          <Badge
            variant="outline"
            className="w-fit rounded-full border-border bg-background/70 px-3 py-1.5 text-xs font-semibold"
          >
            <History className="mr-1 h-3 w-3" />
            Upcoming and in-play
          </Badge>
        </div>
      </section>

      <PredictionsList
        pageSize={50}
        played={false}
        maxElapsedMinutes={100}
        matchId={params.match_id}
        leagueId={params.league_id}
        teamId={params.team_id}
        initialData={initialData ?? undefined}
      />
    </div>
  );
}

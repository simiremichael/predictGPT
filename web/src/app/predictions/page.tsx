import { History } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { PredictionsList } from "@/components/predictions/predictions-list";

interface PredictionsPageProps {
  searchParams: Promise<{
    match_id?: string;
    league_id?: string;
    team_id?: string;
  }>;
}

export const revalidate = 60;

export const metadata = {
  title: "Predictions | Football AI",
  description: "Browse predictions for unfinished football matches.",
};

export default async function PredictionsPage({
  searchParams,
}: PredictionsPageProps) {
  const params = await searchParams;
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
      />
    </div>
  );
}

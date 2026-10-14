import { History } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { PredictionsList } from "@/components/predictions/predictions-list";

export const revalidate = 60;

export const metadata = {
  title: "Results | Football AI",
  description: "Completed football matches and their saved predictions.",
};

export default function ResultsPage() {
  return (
    <div className="space-y-6">
      <section className="surface-card rounded-[1.75rem] p-5 sm:p-6">
        <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="section-kicker mb-2">Match outcomes</p>
            <h1 className="text-3xl font-black tracking-[-0.06em] text-foreground">
              Results
            </h1>
            <p className="mt-2 text-sm text-muted-foreground">
              Matches with final scores, shown after 100 minutes from kickoff
            </p>
          </div>
          <Badge
            variant="outline"
            className="w-fit rounded-full border-border bg-background/70 px-3 py-1.5 text-xs font-semibold"
          >
            <History className="mr-1 h-3 w-3" />
            Played 100+ min
          </Badge>
        </div>
      </section>

      <PredictionsList
        pageSize={50}
        played
        minElapsedMinutes={100}
        newestFirst
      />
    </div>
  );
}

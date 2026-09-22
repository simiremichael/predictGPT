import { api } from "@/lib/api";
import { LoadingState, EmptyState } from "@/components/loading-states";
import { Badge } from "@/components/ui/badge";
import type { League } from "@/types/models";
import Link from "next/link";
import { Trophy } from "lucide-react";

export const revalidate = 60;

export const metadata = {
  title: "Leagues | Football AI",
  description: "Browse football leagues and standings.",
};

export default async function LeaguesPage() {
  let result;
  let error = false;

  try {
    result = await api.listLeagues({ page_size: 50 });
  } catch {
    error = true;
  }

  if (error) {
    return <LoadingState message="Loading leagues..." />;
  }

  if (!result) return null;

  if (result.data.length === 0) {
    return (
      <EmptyState
        title="No leagues found"
        description="No football leagues are currently available."
      />
    );
  }

  return (
    <div className="space-y-6">
      <section className="surface-card rounded-[1.75rem] p-5 sm:p-6">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="section-kicker mb-2">Directory</p>
            <h1 className="text-3xl font-black tracking-[-0.06em] text-foreground">
              Leagues
            </h1>
          </div>
          <Badge
            variant="outline"
            className="w-fit rounded-full border-primary/20 bg-primary/5 px-3 py-1.5 text-xs font-semibold text-primary"
          >
            {result.meta.total} leagues available
          </Badge>
        </div>
      </section>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {result.data.map((league: League) => (
          <Link
            key={league.id}
            href={`/leagues/${league.id}`}
            className="group block"
          >
            <div className="surface-card flex h-full flex-col rounded-[1.5rem] p-4 transition-all duration-200 hover:-translate-y-1 hover:shadow-[0_20px_44px_rgba(15,23,42,0.08)]">
              <div className="flex items-center gap-3">
                <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-gradient-to-br from-primary/12 to-cyan-500/10 text-primary ring-1 ring-primary/10">
                  <Trophy className="h-5 w-5" />
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="truncate font-bold tracking-tight text-foreground transition-colors group-hover:text-primary">
                    {league.name}
                  </h3>
                  {league.country && (
                    <p className="truncate text-sm text-muted-foreground">
                      {league.country}
                    </p>
                  )}
                </div>
              </div>
              <div className="mt-4 border-t border-border/80 pt-3">
                <Badge
                  variant={league.is_active ? "default" : "secondary"}
                  className="text-xs font-semibold"
                >
                  {league.is_active ? "Active" : "Inactive"}
                </Badge>
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}

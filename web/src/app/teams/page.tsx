import { Suspense } from "react";
import Link from "next/link";
import { Search } from "lucide-react";
import { api } from "@/lib/api";
import { LoadingState, EmptyState } from "@/components/loading-states";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { Team } from "@/types/models";

export const revalidate = 60;

export const metadata = {
  title: "Teams | Football AI",
  description: "Browse football teams across all leagues.",
};

interface TeamsPageProps {
  searchParams: Promise<{
    league_id?: string;
    search?: string;
    page?: string;
    page_size?: string;
  }>;
}

export default async function TeamsPage({ searchParams }: TeamsPageProps) {
  const params = await searchParams;
  const page = parseInt(params.page || "1", 10);
  const pageSize = parseInt(params.page_size || "50", 10);

  return (
    <div className="space-y-6">
      <section className="surface-card rounded-[1.75rem] p-5 sm:p-6">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="section-kicker mb-2">Directory</p>
            <h1 className="text-3xl font-black tracking-[-0.06em] text-foreground">
              Teams
            </h1>
            <p className="mt-2 text-sm text-muted-foreground">
              Browse football teams across all leagues
            </p>
          </div>
        </div>
      </section>

      <TeamsFilters
        currentLeague={params.league_id}
        currentSearch={params.search}
      />

      <Suspense fallback={<LoadingState message="Loading teams..." />}>
        <TeamsList
          page={page}
          pageSize={pageSize}
          leagueId={params.league_id}
          search={params.search}
        />
      </Suspense>
    </div>
  );
}

function TeamsFilters({
  currentLeague,
  currentSearch,
}: {
  currentLeague?: string;
  currentSearch?: string;
}) {
  return (
    <form method="GET" className="flex items-center gap-3">
      <div className="flex-1">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            name="search"
            type="search"
            defaultValue={currentSearch}
            placeholder="Search teams..."
            className="w-full rounded-2xl border border-border bg-card/80 pl-10 pr-3 py-2.5 text-sm shadow-sm transition-all focus:border-primary/40 focus:outline-none focus:ring-2 focus:ring-primary/10"
            minLength={2}
          />
        </div>
      </div>

      {currentLeague && (
        <Badge
          variant="secondary"
          className="rounded-full px-3 py-1.5 text-xs font-semibold"
        >
          League: {currentLeague}
        </Badge>
      )}
    </form>
  );
}

async function TeamsList({
  page,
  pageSize,
  leagueId,
  search,
}: {
  page: number;
  pageSize: number;
  leagueId?: string;
  search?: string;
}) {
  let result: { data: Team[]; meta: { total: number } } | null = null;
  let error: boolean = false;

  try {
    result = await api.listTeams({
      league_id: leagueId,
      search: search,
      page,
      page_size: pageSize,
    });
  } catch {
    error = true;
  }

  if (error) {
    return (
      <EmptyState
        title="Failed to load teams"
        description="Please try again later."
      />
    );
  }

  if (!result) return null;

  if (result.data.length === 0) {
    return (
      <EmptyState
        title="No teams found"
        description={
          search ? `No teams matching "${search}"` : "No teams available."
        }
      />
    );
  }

  return (
    <Card className="surface-card rounded-[1.5rem]">
      <CardHeader>
        <CardTitle className="text-xl font-black tracking-[-0.04em] text-foreground">
          {result.meta.total} teams found
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border">
                <th className="py-3 text-left text-[10px] font-bold uppercase tracking-[0.14em] text-muted-foreground">
                  Team
                </th>
                <th className="py-3 text-left text-[10px] font-bold uppercase tracking-[0.14em] text-muted-foreground">
                  Short
                </th>
                <th className="py-3 text-left text-[10px] font-bold uppercase tracking-[0.14em] text-muted-foreground">
                  Country
                </th>
                <th className="py-3 text-center text-[10px] font-bold uppercase tracking-[0.14em] text-muted-foreground">
                  Active
                </th>
              </tr>
            </thead>
            <tbody>
              {result.data.map((team: Team) => (
                <tr
                  key={team.id}
                  className="border-b border-border/50 hover:bg-accent/40"
                >
                  <td className="py-3">
                    <Link
                      href={`/teams/${team.id}`}
                      className="font-semibold text-foreground hover:text-primary"
                    >
                      {team.name}
                    </Link>
                  </td>
                  <td className="py-3 text-muted-foreground">
                    {team.short_name || "-"}
                  </td>
                  <td className="py-3 text-muted-foreground">
                    {team.country || "-"}
                  </td>
                  <td className="py-3 text-center">
                    {team.is_active ? (
                      <Badge
                        variant="default"
                        className="text-xs font-semibold"
                      >
                        Yes
                      </Badge>
                    ) : (
                      <Badge
                        variant="secondary"
                        className="text-xs font-semibold"
                      >
                        No
                      </Badge>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}

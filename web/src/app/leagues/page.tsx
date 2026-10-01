import { Trophy } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { LeaguesList } from "@/components/leagues/leagues-list";
import { LoadingState } from "@/components/loading-states";

interface LeaguesPageProps {
  searchParams: Promise<{
    page?: string;
    page_size?: string;
    country?: string;
    is_active?: string;
  }>;
}

export const metadata = {
  title: "Leagues | Football AI",
  description: "Browse football leagues and standings.",
};

export default async function LeaguesPage({ searchParams }: LeaguesPageProps) {
  const params = await searchParams;
  const page = parseInt(params.page || "1", 10);
  const pageSize = parseInt(params.page_size || "20", 10);
  const country = params.country || "";
  const isActive = params.is_active !== "false";

  return (
    <div className="space-y-6">
      <LeaguesList
        initialPage={page}
        initialPageSize={pageSize}
        initialCountry={country}
        initialIsActive={isActive}
      />
    </div>
  );
}

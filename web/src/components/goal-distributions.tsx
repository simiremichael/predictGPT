import { cn } from "@/lib/utils";
import type { GoalDistributions } from "@/types/models";
import { GoalDistribution } from "@/components/top-scorelines";

interface GoalDistributionsProps {
  distributions: GoalDistributions;
  homeTeam: string;
  awayTeam: string;
  className?: string;
}

export function GoalDistributionsView({
  distributions,
  homeTeam,
  awayTeam,
  className,
}: GoalDistributionsProps) {
  return (
    <div className={cn("grid gap-6 sm:grid-cols-2", className)}>
      <GoalDistribution
        distribution={distributions.home.probabilities}
        mean={distributions.home.mean}
        label={homeTeam}
      />
      <GoalDistribution
        distribution={distributions.away.probabilities}
        mean={distributions.away.mean}
        label={awayTeam}
      />
    </div>
  );
}

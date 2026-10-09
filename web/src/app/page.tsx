import Link from "next/link";
import {
  ArrowRight,
  BarChart3,
  CalendarDays,
  ChevronRight,
  Globe2,
  Shield,
  Sparkles,
  Star,
  Target,
  Trophy,
  TrendingUp,
} from "lucide-react";
import { api } from "@/lib/api";
import { MatchCard } from "@/components/match-card";
import { EmptyState } from "@/components/loading-states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type {
  League,
  MatchBrief,
  PredictionHistoryItem,
  Team,
} from "@/types/models";

export const revalidate = 60;

export const metadata = {
  title: "Football AI - AI-Powered Football Match Predictions",
  description:
    "Probabilistic football match predictions using Poisson models with optional AI research integration.",
};

const countryHighlights = [
  "England",
  "Spain",
  "Italy",
  "Germany",
  "France",
  "Europe",
];

export default async function HomePage() {
  const [leaguesResult, upcomingResult, predictionsResult, teamsResult] =
    await Promise.allSettled([
      api.listLeagues({ is_active: true, page_size: 6 }),
      api.getUpcomingMatches({ days: 7, page_size: 6 }),
      api.getPredictions({ page_size: 6 }),
      api.listTeams({ is_active: true, page_size: 6 }),
    ]);

  const featuredLeagues =
    leaguesResult.status === "fulfilled" ? leaguesResult.value.data : [];
  const upcomingMatches =
    upcomingResult.status === "fulfilled" ? upcomingResult.value.data : [];
  const recentPredictions =
    predictionsResult.status === "fulfilled"
      ? predictionsResult.value.data
      : [];
  const featuredTeams =
    teamsResult.status === "fulfilled" ? teamsResult.value.data : [];

  return (
    <div className="space-y-10 sm:space-y-12">
      <HeroSection />
      <StatsPreview />

      <section className="grid gap-5 xl:grid-cols-[1.1fr_0.9fr]">
        <div className="surface-card rounded-[1.9rem] p-5 sm:p-6">
          <div className="mb-5 flex items-center justify-between gap-3">
            <div>
              <p className="section-kicker mb-2">Leagues</p>
              <h2 className="text-2xl font-black tracking-[-0.06em] text-foreground">
                Country-first league watch
              </h2>
            </div>
            <Link
              href="/leagues"
              className="inline-flex items-center gap-1 text-sm font-semibold text-primary hover:text-primary/80"
            >
              Explore all
              <ChevronRight className="h-4 w-4" />
            </Link>
          </div>

          <div className="mb-4 flex flex-wrap gap-2">
            {countryHighlights.map((country) => (
              <Badge
                key={country}
                variant="outline"
                className="rounded-full border-border bg-background/70 px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.12em] text-foreground"
              >
                {country}
              </Badge>
            ))}
          </div>

          <div className="grid gap-3">
            {featuredLeagues.length > 0 ? (
              featuredLeagues.map((league: League) => (
                <Link
                  key={league.id}
                  href={`/leagues/${league.id}`}
                  className="group flex items-center justify-between rounded-2xl border border-border bg-background/60 px-4 py-3 transition-all hover:border-primary/20 hover:bg-primary/5"
                >
                  <div>
                    <p className="text-sm font-semibold text-foreground">
                      {league.name}
                    </p>
                    <p className="text-xs uppercase tracking-[0.12em] text-muted-foreground">
                      {league.country || "Global"}
                    </p>
                  </div>
                  <div className="flex items-center gap-2 text-primary">
                    <span className="rounded-full bg-primary/10 px-2.5 py-1 text-xs font-bold">
                      Live
                    </span>
                    <ChevronRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
                  </div>
                </Link>
              ))
            ) : (
              <EmptyState
                title="No leagues available"
                description="League data is not available right now."
                className="py-8"
              />
            )}
          </div>
        </div>

        <div className="surface-card rounded-[1.9rem] p-5 sm:p-6">
          <p className="section-kicker mb-2">Why this model</p>
          <h2 className="text-2xl font-black tracking-[-0.06em] text-foreground">
            Transparent probability, not hype.
          </h2>
          <div className="mt-5 space-y-3">
            {[
              "Research-backed inputs with team form and xG signals",
              "Match-level predictions that stay explainable and auditable",
              "League-aware recommendations for faster decision making",
            ].map((item) => (
              <div
                key={item}
                className="flex items-start gap-3 rounded-2xl border border-border bg-background/60 p-3"
              >
                <span className="mt-0.5 flex h-7 w-7 items-center justify-center rounded-full bg-primary/10 text-primary">
                  <Target className="h-4 w-4" />
                </span>
                <p className="text-sm leading-6 text-muted-foreground">
                  {item}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section>
        <div className="mb-6 flex items-end justify-between gap-4">
          <div>
            <p className="section-kicker mb-2">Fixtures</p>
            <h2 className="text-2xl font-black tracking-[-0.06em] text-foreground">
              Upcoming matches
            </h2>
          </div>
          <Link
            href="/matches?upcoming=true"
            className="text-sm font-medium text-primary underline-offset-4 hover:underline"
          >
            View all
          </Link>
        </div>
        {upcomingMatches.length > 0 ? (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {upcomingMatches.map((match: MatchBrief) => (
              <MatchCard key={match.id} match={match} showPrediction={false} />
            ))}
          </div>
        ) : (
          <EmptyState
            title="No upcoming fixtures"
            description="No upcoming matches are available right now."
          />
        )}
      </section>

      <section className="grid gap-5 lg:grid-cols-[0.95fr_1.05fr]">
        <div className="surface-card rounded-[1.9rem] p-5 sm:p-6">
          <div className="mb-5 flex items-center justify-between gap-3">
            <div>
              <p className="section-kicker mb-2">Clubs</p>
              <h2 className="text-2xl font-black tracking-[-0.06em] text-foreground">
                Teams in focus
              </h2>
            </div>
            <Link
              href="/teams"
              className="text-sm font-medium text-primary underline-offset-4 hover:underline"
            >
              Browse all
            </Link>
          </div>

          <div className="space-y-3">
            {featuredTeams.length > 0 ? (
              featuredTeams.map((team: Team) => (
                <Link
                  key={team.id}
                  href={`/teams/${team.id}`}
                  className="flex items-center justify-between rounded-2xl border border-border bg-background/60 px-3 py-3 transition-all hover:border-primary/20 hover:bg-primary/5"
                >
                  <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-primary/12 to-cyan-500/10 text-sm font-black text-primary ring-1 ring-primary/10">
                      {team.short_name?.slice(0, 2)?.toUpperCase() ||
                        team.name.slice(0, 2).toUpperCase()}
                    </div>
                    <div>
                      <p className="font-semibold text-foreground">
                        {team.name}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {team.country || "Global"}
                      </p>
                    </div>
                  </div>
                  <Star className="h-4 w-4 text-primary" />
                </Link>
              ))
            ) : (
              <EmptyState
                title="No teams found"
                description="Team data is currently unavailable."
                className="py-8"
              />
            )}
          </div>
        </div>

        <div className="surface-card rounded-[1.9rem] p-5 sm:p-6">
          <div className="mb-5 flex items-center justify-between gap-3">
            <div>
              <p className="section-kicker mb-2">Model</p>
              <h2 className="text-2xl font-black tracking-[-0.06em] text-foreground">
                Latest predictions
              </h2>
            </div>
            <Link
              href="/predictions"
              className="text-sm font-medium text-primary underline-offset-4 hover:underline"
            >
              View all
            </Link>
          </div>

          <div className="space-y-3">
            {recentPredictions.length > 0 ? (
              recentPredictions.map((item: PredictionHistoryItem) => (
                <Link
                  key={item.prediction_id}
                  href={`/predictions/${item.prediction_id}`}
                  className="block rounded-2xl border border-border bg-background/60 p-3 transition-all hover:border-primary/20 hover:bg-primary/5"
                >
                   <div className="flex items-center justify-between gap-3">
                     <div>
                       <p className="font-semibold text-foreground">
                         {item.match_home_team} vs {item.match_away_team}
                       </p>
                       <p className="text-xs text-muted-foreground">
                         {item.match_kickoff
                           ? new Date(item.match_kickoff).toLocaleDateString()
                           : new Date(item.generated_at).toLocaleDateString()}{" "}
                         • {item.model_version}
                       </p>
                     </div>

                     <div className="flex items-center gap-4">
                       <div className="flex gap-2 text-center">
                         <div>
                           <span className="text-[9px] uppercase text-muted-foreground">H</span>
                           <p className="text-sm font-bold">
                             {item.home_probability
                               ? `${Math.round(item.home_probability * 100)}%`
                               : "—"}
                           </p>
                         </div>
                         <div>
                           <span className="text-[9px] uppercase text-muted-foreground">D</span>
                           <p className="text-sm font-bold">
                             {item.draw_probability
                               ? `${Math.round(item.draw_probability * 100)}%`
                               : "—"}
                           </p>
                         </div>
                         <div>
                           <span className="text-[9px] uppercase text-muted-foreground">A</span>
                           <p className="text-sm font-bold">
                             {item.away_probability
                               ? `${Math.round(item.away_probability * 100)}%`
                               : "—"}
                           </p>
                         </div>
                       </div>
                       <div className="flex gap-2 text-center">
                         <div>
                           <span className="text-[9px] uppercase text-muted-foreground">O 2.5</span>
                           <p className="text-sm font-bold">
                             {item.over_2_5_probability
                               ? `${Math.round(item.over_2_5_probability * 100)}%`
                               : "—"}
                           </p>
                         </div>
                         <div>
                           <span className="text-[9px] uppercase text-muted-foreground">BTTS</span>
                           <p className="text-sm font-bold">
                             {item.btts_probability
                               ? `${Math.round(item.btts_probability * 100)}%`
                               : "—"}
                           </p>
                         </div>
                       </div>
                       <Badge
                         variant="default"
                         className="rounded-full px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.12em]"
                       >
                         {(item.model_confidence * 100).toFixed(0)}%
                       </Badge>
                     </div>
                  </div>
                </Link>
              ))
            ) : (
              <EmptyState
                title="No predictions yet"
                description="No model-generated predictions are available."
              />
            )}
          </div>
        </div>
      </section>
    </div>
  );
}

function HeroSection() {
  return (
    <section className="relative overflow-hidden">
      <div className="absolute inset-0 -z-10 bg-[radial-gradient(circle_at_left_top,rgba(16,185,129,0.18),transparent_25%),radial-gradient(circle_at_right_center,rgba(59,130,246,0.12),transparent_28%),radial-gradient(circle_at_bottom,rgba(250,204,21,0.08),transparent_22%)]" />
      <div className="glass-panel relative overflow-hidden rounded-[2rem] p-6 shadow-[0_30px_80px_rgba(15,23,42,0.09)] sm:p-8 lg:p-10">
        <div className="grid items-center gap-8 lg:grid-cols-[1.15fr_0.85fr]">
          <div className="space-y-6 text-center lg:text-left">
            <Badge
              variant="secondary"
              className="inline-flex items-center gap-2 border border-primary/20 bg-primary/10 px-3 py-1 text-[11px] font-bold uppercase tracking-[0.16em] text-primary"
            >
              <Sparkles className="h-3.5 w-3.5" />
              Poisson Model v1.0.0
            </Badge>

            <div className="space-y-4">
              <h1 className="text-4xl font-black tracking-[-0.08em] text-foreground sm:text-5xl md:text-6xl">
                <span className="bg-gradient-to-r from-primary via-emerald-500 to-cyan-500 bg-clip-text text-transparent">
                  Football
                </span>{" "}
                <span className="text-foreground">AI</span>
              </h1>
              <p className="mx-auto max-w-xl text-base text-muted-foreground sm:text-lg lg:mx-0">
                Serious football intelligence for modern fans and analysts —
                combining probability models, live team signal, and AI research
                to surface sharper betting and match insights.
              </p>
            </div>

            <div className="flex flex-wrap justify-center gap-3 lg:justify-start">
              <Link href="/matches">
                <Button
                  size="lg"
                  className="rounded-full px-5 shadow-[0_16px_32px_rgba(13,128,87,0.25)]"
                >
                  Browse Matches
                  <ArrowRight className="h-4 w-4" />
                </Button>
              </Link>
              <Link href="/predictions">
                <Button
                  variant="outline"
                  size="lg"
                  className="rounded-full px-5"
                >
                  View Predictions
                </Button>
              </Link>
              <Link href="/teams">
                <Button variant="ghost" size="lg" className="rounded-full px-5">
                  Teams Directory
                </Button>
              </Link>
            </div>

            <div className="flex flex-wrap items-center justify-center gap-3 pt-2 lg:justify-start">
              {["xG & Shot Maps", "Live Form", "AI Research"].map((pill) => (
                <span
                  key={pill}
                  className="rounded-full border border-border bg-card/60 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground"
                >
                  {pill}
                </span>
              ))}
            </div>
          </div>

          <div className="relative">
            <div className="absolute -left-8 -top-8 h-24 w-24 rounded-full bg-primary/15 blur-3xl" />
            <div className="absolute -bottom-6 right-6 h-28 w-28 rounded-full bg-cyan-500/10 blur-3xl" />

            <div className="relative overflow-hidden rounded-[1.8rem] border border-border/80 bg-gradient-to-br from-primary/10 via-card to-card p-5 shadow-[0_26px_52px_rgba(15,23,42,0.10)]">
              <div className="mb-5 flex items-center justify-between">
                <div>
                  <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-muted-foreground">
                    Model edge
                  </p>
                  <h3 className="mt-1 text-2xl font-black tracking-[-0.06em] text-foreground">
                    Smart snapshot
                  </h3>
                </div>
                <div className="rounded-full border border-emerald-500/25 bg-emerald-500/10 px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.14em] text-emerald-600">
                  Live
                </div>
              </div>

              <div className="space-y-3">
                {[
                  {
                    label: "Home win",
                    value: "58%",
                    tone: "bg-emerald-500/12 text-emerald-600",
                  },
                  {
                    label: "Draw",
                    value: "24%",
                    tone: "bg-amber-500/12 text-amber-600",
                  },
                  {
                    label: "Away win",
                    value: "18%",
                    tone: "bg-cyan-500/12 text-cyan-600",
                  },
                ].map((item) => (
                  <div
                    key={item.label}
                    className="flex items-center justify-between rounded-2xl border border-border bg-background/60 px-3 py-2.5"
                  >
                    <span className="text-sm font-medium text-muted-foreground">
                      {item.label}
                    </span>
                    <span
                      className={`rounded-full px-2.5 py-1 text-sm font-bold ${item.tone}`}
                    >
                      {item.value}
                    </span>
                  </div>
                ))}
              </div>

              <div className="mt-5 rounded-[1.3rem] border border-border bg-card/80 p-4">
                <div className="mb-2 flex items-center justify-between text-[10px] font-bold uppercase tracking-[0.16em] text-muted-foreground">
                  <span>Best scoreline</span>
                  <span>2.1 xG</span>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <div className="text-3xl font-black tracking-[-0.07em] text-foreground">
                    2 - 1
                  </div>
                  <div className="rounded-full bg-primary/10 px-2.5 py-1 text-[11px] font-bold text-primary">
                    76% confidence
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function StatsPreview() {
  const stats = [
    { label: "Leagues Covered", value: "26+", icon: Trophy },
    { label: "Teams Tracked", value: "500+", icon: Shield },
    { label: "Daily Fixtures", value: "1K+", icon: CalendarDays },
    { label: "Avg. Edge", value: "+7.8%", icon: TrendingUp },
  ];

  return (
    <section>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {stats.map((stat) => (
          <div
            key={stat.label}
            className="surface-card flex items-center justify-center gap-3 rounded-[1.4rem] p-4 text-center transition-transform duration-200 hover:-translate-y-0.5"
          >
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-gradient-to-br from-primary/12 to-cyan-500/10 text-primary ring-1 ring-primary/10">
              <stat.icon className="h-5 w-5" />
            </div>
            <div>
              <span className="block text-2xl font-black tracking-[-0.06em] text-foreground">
                {stat.value}
              </span>
              <p className="text-sm text-muted-foreground">{stat.label}</p>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function FeaturesSection() {
  const features = [
    {
      title: "Poisson Model",
      description:
        "Mathematically transparent score probability matrix using league-specific attack and defense strengths.",
      icon: TrendingUp,
    },
    {
      title: "AI Research Integration",
      description:
        "Web-sourced injury reports, lineups, and team news adjust predictions within bounded parameters.",
      icon: Sparkles,
    },
    {
      title: "Market Probabilities",
      description:
        "Over/Under, BTTS, clean sheets, and double chance markets derived directly from the model.",
      icon: BarChart3,
    },
  ];

  return (
    <section className="pt-2">
      <div className="mb-6 flex items-end justify-between gap-4">
        <div>
          <p className="section-kicker mb-2">How it works</p>
          <h2 className="text-2xl font-black tracking-[-0.06em] sm:text-3xl">
            A sharper way to evaluate football probability.
          </h2>
        </div>
      </div>

      <div className="grid gap-5 sm:grid-cols-3">
        {features.map((feature) => (
          <div
            key={feature.title}
            className="surface-card flex h-full flex-col rounded-[1.6rem] p-5 text-left transition-all duration-300 hover:-translate-y-1"
          >
            <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-primary/12 to-cyan-500/10 text-primary ring-1 ring-primary/10 shadow-[0_10px_24px_rgba(13,128,87,0.10)]">
              <feature.icon className="h-5 w-5" />
            </div>
            <h3 className="mb-2 text-lg font-bold tracking-tight text-foreground">
              {feature.title}
            </h3>
            <p className="text-sm leading-6 text-muted-foreground">
              {feature.description}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}

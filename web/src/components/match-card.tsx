"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import { Calendar, Clock } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  formatDateTime,
  formatTime,
  getMatchStatusColor,
  getMatchStatusLabel,
  timeToKickoff,
} from "@/lib/formatters";
import type { MatchBrief } from "@/types/models";
import { Badge } from "@/components/ui/badge";

interface MatchCardProps {
  match: MatchBrief;
  prediction?: {
    home_probability: number;
    draw_probability: number;
    away_probability: number;
    model_confidence: number;
    top_scoreline?: { home_goals: number; away_goals: number };
  } | null;
  showPrediction?: boolean;
  variant?: "default" | "compact";
}

export function MatchCard({
  match,
  prediction,
  showPrediction = true,
  variant: _variant = "default",
}: MatchCardProps) {
  const isLive = match.status === "live";
  const isFinished = match.is_finished;
  const kickoffAt = match.kickoff_at ? new Date(match.kickoff_at) : null;

  const cardClasses = cn(
    "surface-card group relative block overflow-hidden rounded-[1.6rem] bg-card/90 p-4 transition-all duration-300 hover:-translate-y-1 hover:shadow-[0_24px_50px_rgba(13,128,87,0.10)]",
    isLive && "border-red-500/40 shadow-[0_18px_40px_rgba(239,68,68,0.09)]",
    isFinished && "opacity-85",
  );

  const teamDisplay = (name?: string | null) => {
    if (!name) return "TBD";
    return name.length > 22 ? `${name.slice(0, 20)}..` : name;
  };

  return (
    <Link href={`/matches/${match.id}`} className={cardClasses}>
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="w-full"
      >
        <div className="mb-4 flex items-center justify-between gap-3">
          <div className="flex min-w-0 items-center gap-2">
            <Badge
              variant={isLive ? "default" : "secondary"}
              className={cn(
                "text-[10px] font-bold uppercase tracking-[0.12em]",
                isLive && "animate-pulse bg-red-500 text-white",
                getMatchStatusColor(match.status),
              )}
            >
              {getMatchStatusLabel(match.status)}
            </Badge>
            {match.league_name && (
              <span className="truncate text-[11px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">
                {match.league_name}
              </span>
            )}
          </div>

          {kickoffAt && (
            <div className="rounded-xl border border-border/80 bg-muted/40 px-2 py-1.5 text-right text-[10px] text-muted-foreground">
              <div className="flex items-center justify-end gap-1">
                <Calendar className="h-3 w-3" />
                {formatDateTime(kickoffAt)}
              </div>
              {!isFinished && kickoffAt && (
                <div className="mt-0.5 flex items-center justify-end gap-1">
                  <Clock className="h-3 w-3" />
                  {timeToKickoff(kickoffAt)}
                </div>
              )}
              {isFinished && kickoffAt && (
                <span className="text-[10px]">{formatTime(kickoffAt)}</span>
              )}
            </div>
          )}
        </div>

        <div className="space-y-3">
          <div className="flex items-center justify-between gap-3 rounded-2xl border border-border/80 bg-muted/30 px-3 py-2.5">
            <div className="flex min-w-0 flex-1 items-center gap-3">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-extrabold text-primary ring-1 ring-primary/10">
                {teamDisplay(match.home_team_name)?.charAt(0)}
              </div>
              <span className="truncate font-semibold tracking-tight text-foreground">
                {teamDisplay(match.home_team_name)}
              </span>
            </div>

            <div className="flex items-center gap-2 px-2 text-sm font-bold text-muted-foreground">
              {isFinished ? (
                <span className="flex items-center gap-2 text-lg font-black text-foreground">
                  {match.home_score} - {match.away_score}
                </span>
              ) : (
                <span className="rounded-md bg-background px-2 py-1 text-[10px] font-extrabold uppercase tracking-[0.12em] text-foreground ring-1 ring-border">
                  VS
                </span>
              )}
            </div>

            <div className="flex min-w-0 flex-1 items-center justify-end gap-3">
              <span className="truncate font-semibold tracking-tight text-foreground">
                {teamDisplay(match.away_team_name)}
              </span>
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-extrabold text-primary ring-1 ring-primary/10">
                {teamDisplay(match.away_team_name)?.charAt(0)}
              </div>
            </div>
          </div>
        </div>

        {showPrediction && prediction && !isFinished && (
          <div className="mt-4 border-t border-border/80 pt-3">
            <div className="grid grid-cols-3 gap-2 text-center">
              <div className="rounded-xl bg-muted/40 px-2 py-2">
                <div className="text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
                  Home
                </div>
                <div className="mt-1 text-sm font-bold text-foreground">
                  {Math.round(prediction.home_probability * 100)}%
                </div>
              </div>
              <div className="rounded-xl bg-muted/40 px-2 py-2">
                <div className="text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
                  Draw
                </div>
                <div className="mt-1 text-sm font-bold text-foreground">
                  {Math.round(prediction.draw_probability * 100)}%
                </div>
              </div>
              <div className="rounded-xl bg-muted/40 px-2 py-2">
                <div className="text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
                  Away
                </div>
                <div className="mt-1 text-sm font-bold text-foreground">
                  {Math.round(prediction.away_probability * 100)}%
                </div>
              </div>
            </div>
            {prediction.top_scoreline && (
              <div className="mt-3 text-center text-[11px] font-medium text-muted-foreground">
                Best: {prediction.top_scoreline.home_goals}-
                {prediction.top_scoreline.away_goals}
              </div>
            )}
          </div>
        )}
      </motion.div>
    </Link>
  );
}

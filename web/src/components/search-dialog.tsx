"use client";

import { useState, useEffect, useRef } from "react";
import { Search, X, Clock, Loader2 } from "lucide-react";
import { Input } from "@/components/ui/input";
import type { SearchResultItem } from "@/types/models";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

interface SearchDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function SearchDialog({ open, onOpenChange }: SearchDialogProps) {
  const [query, setQuery] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open) {
      inputRef.current?.focus();
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  useEffect(() => {
    const handleKeydown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onOpenChange(false);
        setQuery("");
      }
    };

    if (open) {
      document.addEventListener("keydown", handleKeydown);
    }
    return () => document.removeEventListener("keydown", handleKeydown);
  }, [open, onOpenChange]);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dialogRef.current && !dialogRef.current.contains(e.target as Node)) {
        onOpenChange(false);
      }
    };

    if (open) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open, onOpenChange]);

  const { data: searchResults, isPending } = useQuery({
    queryKey: ["search", query],
    queryFn: () => api.search({ q: query, limit: 20 }),
    enabled: query.length >= 2,
    staleTime: 30000,
  });

  const isLoading = isPending && query.length >= 2;
  const hasResults = searchResults && query.length > 0;

  const recentSearches = ["Arsenal", "Manchester City", "Premier League"];

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-[calc(4rem+1px)]">
      <div
        className="absolute inset-0 bg-background/60 backdrop-blur-sm"
        aria-hidden="true"
      />
      <div
        ref={dialogRef}
        className="relative mx-auto w-full max-w-2xl rounded-xl border border-border bg-card shadow-xl"
      >
        <div className="border-b border-border p-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              ref={inputRef}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search teams, leagues, matches..."
              className="border-0 pl-10 pr-10 shadow-none focus-visible:ring-0 focus-visible:ring-offset-0"
            />
            {query && (
              <button
                onClick={() => setQuery("")}
                className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-muted-foreground hover:text-foreground"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>
        </div>

        <div className="max-h-96 overflow-y-auto">
          {isLoading ? (
            <div className="p-6 text-center">
              <Loader2 className="mx-auto h-6 w-6 animate-spin text-muted-foreground" />
              <p className="mt-2 text-sm text-muted-foreground">
                Searching for &ldquo;{query}&rdquo;...
              </p>
            </div>
          ) : hasResults && searchResults ? (
            <div className="p-2">
              {searchResults.teams.length > 0 && (
                <div className="mb-2">
                  <h3 className="px-3 text-xs font-semibold text-muted-foreground">
                    Teams
                  </h3>
                  {searchResults.teams.slice(0, 5).map((team) => (
                    <SearchResult
                      key={team.id}
                      item={{
                        id: team.id,
                        type: "team",
                        name: team.name as string,
                        subtitle: team.country as string,
                        logo_url: team.logo_url as string,
                      }}
                      onSelect={() => onOpenChange(false)}
                    />
                  ))}
                </div>
              )}
              {searchResults.leagues.length > 0 && (
                <div className="mb-2">
                  <h3 className="px-3 text-xs font-semibold text-muted-foreground">
                    Leagues
                  </h3>
                  {searchResults.leagues.slice(0, 5).map((league) => (
                    <SearchResult
                      key={league.id}
                      item={{
                        id: league.id,
                        type: "league",
                        name: league.name as string,
                        subtitle: league.country as string,
                      }}
                      onSelect={() => onOpenChange(false)}
                    />
                  ))}
                </div>
              )}
              {searchResults.matches.length > 0 && (
                <div className="mb-2">
                  <h3 className="px-3 text-xs font-semibold text-muted-foreground">
                    Matches
                  </h3>
                  {searchResults.matches.slice(0, 5).map((match) => (
                    <SearchResult
                      key={match.id}
                      item={{
                        id: match.id,
                        type: "match",
                        name: `${match.home_team_name} vs ${match.away_team_name}`,
                        subtitle: match.status as string,
                      }}
                      onSelect={() => onOpenChange(false)}
                    />
                  ))}
                </div>
              )}
            </div>
          ) : query.length === 0 ? (
            <div className="p-4">
              <h3 className="text-xs font-semibold text-muted-foreground">
                Recent searches
              </h3>
              {recentSearches.map((term) => (
                <button
                  key={term}
                  onClick={() => setQuery(term)}
                  className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm hover:bg-accent"
                >
                  <Clock className="h-3 w-3 text-muted-foreground" />
                  {term}
                </button>
              ))}
            </div>
          ) : (
            <div className="p-6 text-center">
              <p className="text-sm text-muted-foreground">
                No results found for &ldquo;{query}&rdquo;
              </p>
            </div>
          )}
        </div>

        <div className="border-t border-border p-2 text-center text-xs text-muted-foreground">
          Press <kbd className="rounded bg-muted px-1.5 py-0.5">ESC</kbd> to
          close
        </div>
      </div>
    </div>
  );
}

function SearchResult({
  item,
  onSelect,
}: {
  item: SearchResultItem;
  onSelect: () => void;
}) {
  return (
    <button
      onClick={onSelect}
      className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left hover:bg-accent"
    >
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded bg-muted">
        {item.logo_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={item.logo_url}
            alt={item.name}
            className="h-6 w-6 object-contain"
          />
        ) : (
          <span className="text-xs font-bold">{item.name?.charAt(0)}</span>
        )}
      </div>
      <div className="flex-1 truncate">
        <p className="font-medium">{item.name}</p>
        {item.subtitle && (
          <p className="text-xs text-muted-foreground truncate">
            {item.subtitle}
          </p>
        )}
      </div>
    </button>
  );
}

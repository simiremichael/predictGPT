import { useState } from "react";
import { StyleSheet, Text, View, ScrollView, TouchableOpacity, RefreshControl } from "react-native";
import { useLocalSearchParams } from "expo-router";
import { useTheme } from "@/lib/theme/provider";
import { api } from "@/lib/api/client";
import { MatchCard } from "@/components/match/MatchCard";
import { LoadingState } from "@/components/common/LoadingState";
import { EmptyState } from "@/components/common/EmptyState";
import { useApiQuery } from "@/hooks/useApiQuery";
import type { Team, MatchBrief } from "@/types";

export default function TeamDetailScreen() {
  const { theme } = useTheme();
  const isDark = theme === "dark";
  const { id } = useLocalSearchParams<{ id: string }>();

  const {
    data: teamData,
    isLoading: teamLoading,
    refetch: refetchTeam,
    isRefetching: teamRefetching,
  } = useApiQuery(["team-detail", id], () => api.getTeam(id));

  const {
    data: matchesData,
    isLoading: matchesLoading,
    refetch: refetchMatches,
  } = useApiQuery(["team-matches", id], () => api.getTeamMatches(id, { page_size: 20 }));

  const {
    data: statsData,
    isLoading: statsLoading,
  } = useApiQuery(["team-stats", id], () => api.getTeamStats(id));

  const team: Team | null = teamData ?? null;
  const matches: MatchBrief[] = matchesData?.data ?? [];
  const stats = statsData?.statistics ?? [];

  const onRefresh = () => {
    refetchTeam();
    refetchMatches();
  };

  if (teamLoading) {
    return <LoadingState fullScreen />;
  }

  if (!team) {
    return (
      <EmptyState title="Team not found" description="The team you're looking for doesn't exist." />
    );
  }

  return (
    <ScrollView
      style={[styles.container, { backgroundColor: isDark ? "#091410" : "#f7f9f7" }]}
      refreshControl={
        <RefreshControl
          refreshing={teamRefetching || matchesLoading}
          onRefresh={onRefresh}
          tintColor={isDark ? "#8bc34a" : "#0d7450"}
          colors={[isDark ? "#8bc34a" : "#0d7450"]}
        />
      }
    >
      <View style={[styles.teamHeader, { backgroundColor: isDark ? "#0f1f19" : "#ffffff" }]}>
        <View style={[styles.logPlaceholder, { backgroundColor: isDark ? "#172b23" : "#eff4f1" }]}>
          <Text style={{ fontSize: 24, color: isDark ? "#9eb1a4" : "#617068" }}>
            {team.short_name?.[0] ?? team.name?.[0] ?? "T"}
          </Text>
        </View>
        <Text style={[styles.teamName, { color: isDark ? "#e7f0eb" : "#121f19" }]}>
          {team.name}
        </Text>
        {team.venue_city && (
          <Text style={[styles.venue, { color: isDark ? "#9eb1a4" : "#617068" }]}>
            {team.venue_city}
          </Text>
        )}
        {team.venue_name && (
          <Text style={[styles.venueName, { color: isDark ? "#9eb1a4" : "#617068" }]}>
            {team.venue_name}
          </Text>
        )}
      </View>

      <View style={[styles.statsSection, { backgroundColor: isDark ? "#0f1f19" : "#ffffff" }]}>
        <Text style={[styles.sectionTitle, { color: isDark ? "#e7f0eb" : "#121f19" }]}>
          Team Statistics
        </Text>
        {statsLoading ? (
          <LoadingState />
        ) : stats && stats.length > 0 ? (
          <View style={styles.statsGrid}>
            {stats.slice(0, 6).map((stat: Record<string, unknown>, index: number) => {
              const key = Object.keys(stat)[0];
              const value = Object.values(stat)[0];
              return (
                <View key={index} style={styles.statItem}>
                  <Text style={[styles.statLabel, { color: isDark ? "#9eb1a4" : "#617068" }]}>
                    {typeof key === "string" ? key.replace(/_/g, " ") : "Stat"}
                  </Text>
                  <Text style={[styles.statValue, { color: isDark ? "#e7f0eb" : "#121f19" }]}>
                    {typeof value === "number" ? value.toFixed(2) : String(value ?? "-")}
                  </Text>
                </View>
              );
            })}
          </View>
        ) : (
          <EmptyState title="No statistics" description="Statistics not available for this team" />
        )}
      </View>

      <View style={styles.matchesSection}>
        <Text style={[styles.sectionTitle, { color: isDark ? "#e7f0eb" : "#121f19" }]}>
          Recent & Upcoming Matches
        </Text>
        {matchesLoading ? (
          <LoadingState />
        ) : matches.length === 0 ? (
          <EmptyState title="No matches" description="No match history for this team" />
        ) : (
          matches.map((match: MatchBrief) => (
            <MatchCard key={match.id} match={match} size="compact" />
          ))
        )}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  teamHeader: {
    alignItems: "center",
    paddingTop: 56,
    paddingBottom: 24,
    gap: 4,
    borderBottomWidth: 1,
    borderBottomColor: "rgba(128,128,128,0.2)",
  },
  logPlaceholder: {
    width: 72,
    height: 72,
    borderRadius: 12,
    alignItems: "center",
    justifyContent: "center",
  },
  teamName: {
    fontSize: 22,
    fontWeight: "800",
    letterSpacing: -0.3,
    marginTop: 8,
  },
  venue: {
    fontSize: 14,
    fontWeight: "600",
  },
  venueName: {
    fontSize: 12,
  },
  statsSection: {
    marginHorizontal: 16,
    marginTop: 16,
    borderRadius: 16,
    borderWidth: 1,
    padding: 16,
    gap: 8,
  },
  matchesSection: {
    paddingHorizontal: 16,
    paddingBottom: 24,
    gap: 8,
    marginTop: 16,
  },
  sectionTitle: {
    fontSize: 15,
    fontWeight: "700",
    marginBottom: 8,
  },
  statsGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 12,
  },
  statItem: {
    flex: 1,
    minWidth: "40%",
    paddingVertical: 8,
    paddingHorizontal: 8,
    borderBottomWidth: 1,
    borderBottomColor: "rgba(128,128,128,0.1)",
  },
  statLabel: {
    fontSize: 10,
    fontWeight: "600",
    textTransform: "uppercase",
    letterSpacing: 0.3,
  },
  statValue: {
    fontSize: 14,
    fontWeight: "700",
    marginTop: 2,
  },
});

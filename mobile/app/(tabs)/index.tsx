import React from "react";
import { StyleSheet, Text, View, ScrollView, RefreshControl, TouchableOpacity } from "react-native";
import { Link } from "expo-router";
import { useTheme } from "@/lib/theme/provider";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { MatchCard } from "@/components/match/MatchCard";
import { SectionHeader } from "@/components/common/SectionHeader";
import { LoadingState } from "@/components/common/LoadingState";
import { EmptyState } from "@/components/common/EmptyState";
import { DataQualityIndicator } from "@/components/prediction/DataQualityIndicator";
import { LeagueCard } from "@/components/league/LeagueCard";
import { useApiQuery } from "@/hooks/useApiQuery";
import { formatDate } from "@/utils";
import type { MatchBrief, League, PredictionHistoryItem } from "@/types";

export default function HomeScreen() {
  const { theme } = useTheme();
  const isDark = theme === "dark";
  const queryClient = useQueryClient();

  const {
    data: upcomingData,
    isLoading: upcomingLoading,
    refetch: refetchUpcoming,
    isRefetching: upcomingRefetching,
  } = useApiQuery(["upcoming-matches"], () => api.getUpcomingMatches({ days: 7 }));

  const {
    data: leaguesData,
    isLoading: leaguesLoading,
  } = useApiQuery(["leagues"], () => api.getLeagues());

  const {
    data: predictionsData,
    isLoading: predictionsLoading,
  } = useApiQuery(["predictions", "recent"], () => api.getPredictionHistory({ page_size: 10 }));

  const upcomingMatches = upcomingData?.data ?? [];
  const leagues = leaguesData?.data ?? [];
  const recentPredictions = predictionsData?.data ?? [];

  const onRefresh = React.useCallback(() => {
    refetchUpcoming();
    queryClient.invalidateQueries({ queryKey: ["leagues"] });
    queryClient.invalidateQueries({ queryKey: ["predictions", "recent"] });
  }, [queryClient]);

  if (upcomingLoading) {
    return <LoadingState fullScreen />;
  }

  return (
    <ScrollView
      style={[styles.container, { backgroundColor: isDark ? "#091410" : "#f7f9f7" }]}
      refreshControl={
        <RefreshControl
          refreshing={upcomingRefetching}
          onRefresh={onRefresh}
          tintColor={isDark ? "#8bc34a" : "#0d7450"}
          colors={[isDark ? "#8bc34a" : "#0d7450"]}
        />
      }
    >
      <View style={styles.header}>
        <Text style={[styles.title, { color: isDark ? "#e7f0eb" : "#121f19" }]}>
          Football AI
        </Text>
        <Text style={[styles.subtitle, { color: isDark ? "#9eb1a4" : "#617068" }]}>
          Machine learning football predictions
        </Text>
      </View>

      <SectionHeader
        title="Upcoming Matches"
        subtitle={formatDate(new Date().toISOString())}
        action={
          <Link href="/matches" asChild>
            <TouchableOpacity>
              <Text style={[styles.actionLink, { color: isDark ? "#8bc34a" : "#0d7450" }]}>
                See all
              </Text>
            </TouchableOpacity>
          </Link>
        }
      />

      {upcomingMatches.length === 0 ? (
        <EmptyState title="No upcoming matches" description="Check back later for the latest fixtures" />
      ) : (
        upcomingMatches.slice(0, 5).map((match: MatchBrief) => (
          <MatchCard key={match.id} match={match} showPrediction={false} size="compact" />
        ))
      )}

      <SectionHeader title="Top Leagues" />
      {leaguesLoading ? (
        <LoadingState />
      ) : leagues.length === 0 ? (
        <EmptyState title="No leagues available" />
      ) : (
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.horizontalScroll}>
          {leagues.slice(0, 6).map((league: League) => (
            <LeagueCard key={league.id} league={league} size="compact" />
          ))}
        </ScrollView>
      )}

      <SectionHeader
        title="Recent Predictions"
        action={
          <Link href="/predictions" asChild>
            <TouchableOpacity>
              <Text style={[styles.actionLink, { color: isDark ? "#8bc34a" : "#0d7450" }]}>
                View all
              </Text>
            </TouchableOpacity>
          </Link>
        }
      />

      {predictionsLoading ? (
        <LoadingState />
      ) : recentPredictions.length === 0 ? (
        <EmptyState title="No predictions yet" description="Check back after matches are analyzed" />
      ) : (
        recentPredictions.map((item: PredictionHistoryItem) => (
          <Link href={`/prediction/${item.match_id}`} key={item.prediction_id} asChild>
            <TouchableOpacity>
              <View
                style={[
                  styles.predictionItem,
                  {
                    backgroundColor: isDark ? "#0f1f19" : "#ffffff",
                    borderColor: isDark ? "#253e33" : "#dce6e0",
                  },
                ]}
              >
                <View style={styles.predictionItemHeader}>
                  <Text
                    style={[styles.predictionMatch, { color: isDark ? "#e7f0eb" : "#121f19" }]}
                    numberOfLines={1}
                  >
                    {item.match_home_team || "Home"} vs {item.match_away_team || "Away"}
                  </Text>
                  <Text style={[styles.predictionDate, { color: isDark ? "#9eb1a4" : "#617068" }]}>
                    {item.generated_at ? formatDate(item.generated_at) : "—"}
                  </Text>
                </View>
                <DataQualityIndicator quality={item.data_quality} size="sm" showLabel={false} style={{ marginHorizontal: 12, marginTop: 8 }} />
              </View>
            </TouchableOpacity>
          </Link>
        ))
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  header: {
    paddingHorizontal: 16,
    paddingTop: 60,
    paddingBottom: 24,
    gap: 4,
  },
  title: {
    fontSize: 32,
    fontWeight: "800",
    letterSpacing: -0.5,
  },
  subtitle: {
    fontSize: 15,
    marginTop: 2,
  },
  actionLink: {
    fontSize: 13,
    fontWeight: "600",
  },
  horizontalScroll: {
    flexDirection: "row",
    gap: 12,
    paddingHorizontal: 16,
  },
  predictionItem: {
    marginHorizontal: 16,
    marginBottom: 16,
    borderRadius: 16,
    borderWidth: 1,
    overflow: "hidden",
  },
  predictionItemHeader: {
    padding: 12,
    paddingBottom: 0,
    gap: 2,
  },
  predictionMatch: {
    fontSize: 13,
    fontWeight: "600",
  },
  predictionDate: {
    fontSize: 11,
  },
});

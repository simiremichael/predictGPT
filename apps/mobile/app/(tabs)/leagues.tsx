import { useState } from "react";
import { StyleSheet, Text, View, ScrollView, TouchableOpacity, RefreshControl } from "react-native";
import { Link } from "expo-router";
import { useTheme } from "@/lib/theme/provider";
import { api } from "@/lib/api/client";
import { LoadingState } from "@/components/common/LoadingState";
import { EmptyState } from "@/components/common/EmptyState";
import { useApiQuery } from "@/hooks/useApiQuery";
import type { League, Standing } from "@/types";

const COUNTRIES = [
  "All",
  "England",
  "Spain",
  "Italy",
  "Germany",
  "France",
  "Portugal",
  "Turkey",
  "Netherlands",
  "Belgium",
];

export default function LeaguesScreen() {
  const { theme } = useTheme();
  const isDark = theme === "dark";
  const [selectedCountry, setSelectedCountry] = useState("All");

  const {
    data: leaguesData,
    isLoading: leaguesLoading,
    refetch: refetchLeagues,
    isRefetching: leaguesRefetching,
  } = useApiQuery(["leagues", selectedCountry], () => {
    if (selectedCountry === "All") {
      return api.getLeagues({ is_active: true });
    }
    return api.getCountryLeaguesList(selectedCountry);
  });

  const leagues: League[] = leaguesData?.data ?? [];

  const onRefresh = () => {
    refetchLeagues();
  };

  if (leaguesLoading) {
    return <LoadingState fullScreen />;
  }

  return (
    <ScrollView
      style={[styles.container, { backgroundColor: isDark ? "#091410" : "#f7f9f7" }]}
      refreshControl={
        <RefreshControl
          refreshing={leaguesRefetching}
          onRefresh={onRefresh}
          tintColor={isDark ? "#8bc34a" : "#0d7450"}
          colors={[isDark ? "#8bc34a" : "#0d7450"]}
        />
      }
    >
      <View style={styles.header}>
        <Text style={[styles.title, { color: isDark ? "#e7f0eb" : "#121f19" }]}>
          Leagues
        </Text>
        <Text style={[styles.subtitle, { color: isDark ? "#9eb1a4" : "#617068" }]}>
          Browse leagues by country
        </Text>
      </View>

      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.countryStrip}>
        <View style={styles.countryRow}>
          {COUNTRIES.map((country) => (
            <TouchableOpacity
              key={country}
              style={[
                styles.countryButton,
                {
                  backgroundColor:
                    selectedCountry === country
                      ? isDark
                        ? "#8bc34a"
                        : "#0d7450"
                      : isDark
                        ? "#172b23"
                        : "#eff4f1",
                },
              ]}
              onPress={() => setSelectedCountry(country)}
            >
              <Text
                style={[
                  styles.countryButtonText,
                  {
                    color:
                      selectedCountry === country
                        ? "#f7fff7"
                        : isDark
                          ? "#e7f0eb"
                          : "#121f19",
                  },
                ]}
              >
                {country}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
      </ScrollView>

      {leagues.length === 0 ? (
        <EmptyState title="No leagues found" description="Try selecting a different country" />
      ) : (
        leagues.map((league: League) => (
          <Link href={`/league/${league.id}`} key={league.id} asChild>
            <TouchableOpacity
              style={[
                styles.leagueCard,
                {
                  backgroundColor: isDark ? "#0f1f19" : "#ffffff",
                  borderColor: isDark ? "#253e33" : "#dce6e0",
                },
              ]}
            >
              <View style={styles.leagueInfo}>
                <Text
                  style={[styles.leagueName, { color: isDark ? "#e7f0eb" : "#121f19" }]}
                  numberOfLines={1}
                >
                  {league.name}
                </Text>
                {league.country && (
                  <Text style={[styles.leagueCountry, { color: isDark ? "#9eb1a4" : "#617068" }]}>
                    {league.country}
                  </Text>
                )}
                {league.tier && (
                  <Text style={[styles.leagueTier, { color: isDark ? "#9eb1a4" : "#617068" }]}>
                    Tier {league.tier}
                  </Text>
                )}
              </View>
              {league.standings_summary && league.standings_summary.length > 0 && (
                <View style={styles.standingsPreview}>
                  {league.standings_summary.slice(0, 4).map((standing: Standing) => (
                    <View key={standing.team_id} style={styles.standingRow}>
                      <Text
                        style={[styles.standingPosition, { color: isDark ? "#9eb1a4" : "#617068" }]}
                      >
                        {standing.position}.
                      </Text>
                      <Text
                        style={[styles.standingTeam, { color: isDark ? "#e7f0eb" : "#121f19" }]}
                        numberOfLines={1}
                      >
                        {standing.team_name}
                      </Text>
                      <Text
                        style={[styles.standingPoints, { color: isDark ? "#9eb1a4" : "#617068" }]}
                      >
                        {standing.points}
                      </Text>
                    </View>
                  ))}
                </View>
              )}
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
    paddingTop: 52,
  },
  header: {
    paddingHorizontal: 16,
    paddingBottom: 16,
    gap: 4,
  },
  title: {
    fontSize: 32,
    fontWeight: "800",
    letterSpacing: -0.5,
  },
  subtitle: {
    fontSize: 14,
    marginTop: 2,
  },
  countryStrip: {
    paddingBottom: 12,
  },
  countryRow: {
    flexDirection: "row",
    gap: 8,
    paddingHorizontal: 16,
  },
  countryButton: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 999,
  },
  countryButtonText: {
    fontSize: 12,
    fontWeight: "600",
  },
  leagueCard: {
    flexDirection: "row",
    marginHorizontal: 16,
    marginBottom: 12,
    borderRadius: 16,
    borderWidth: 1,
    padding: 14,
    gap: 8,
    alignItems: "center",
    justifyContent: "space-between",
  },
  leagueInfo: {
    flex: 1,
    gap: 2,
  },
  leagueName: {
    fontSize: 15,
    fontWeight: "700",
  },
  leagueCountry: {
    fontSize: 12,
  },
  leagueTier: {
    fontSize: 11,
  },
  standingsPreview: {
    alignItems: "flex-end",
    gap: 2,
  },
  standingRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  standingPosition: {
    fontSize: 10,
    width: 20,
  },
  standingTeam: {
    fontSize: 10,
    fontWeight: "600",
    width: 70,
    textAlign: "right",
  },
  standingPoints: {
    fontSize: 10,
    fontWeight: "700",
    width: 30,
    textAlign: "right",
  },
});

import { useState } from "react";
import { StyleSheet, Text, View, ScrollView, TouchableOpacity, RefreshControl } from "react-native";
import { useTheme } from "@/lib/theme/provider";
import { api } from "@/lib/api/client";
import { MatchCard } from "@/components/match/MatchCard";
import { LoadingState } from "@/components/common/LoadingState";
import { EmptyState } from "@/components/common/EmptyState";
import { useApiQuery } from "@/hooks/useApiQuery";
import { useQueryClient } from "@tanstack/react-query";
import type { MatchBrief, League } from "@/types";
import { Picker } from "@react-native-picker/picker";

const DATE_PRESETS = [
  { label: "Today", value: "today" },
  { label: "Tomorrow", value: "tomorrow" },
  { label: "This Week", value: "week" },
  { label: "All Upcoming", value: "upcoming" },
];

export default function MatchesScreen() {
  const { theme } = useTheme();
  const isDark = theme === "dark";
  const queryClient = useQueryClient();

  const [selectedDatePreset, setSelectedDatePreset] = useState("today");
  const [selectedLeague, setSelectedLeague] = useState<string | null>(null);

  const {
    data: todayData,
    isLoading: todayLoading,
    refetch: refetchToday,
  } = useApiQuery(["matches-today", selectedLeague], () =>
    api.getTodayMatches(selectedLeague ? { league_id: selectedLeague } : undefined),
  );

  const {
    data: upcomingData,
    isLoading: upcomingLoading,
    refetch: refetchUpcoming,
  } = useApiQuery(["matches-upcoming", selectedDatePreset, selectedLeague], () => {
    const params: { days?: number; league_id?: string } = {};
    if (selectedDatePreset === "week") params.days = 7;
    if (selectedDatePreset === "upcoming") params.days = 30;
    if (selectedLeague) params.league_id = selectedLeague;
    return api.getUpcomingMatches(params);
  });

  const {
    data: leaguesData,
    isLoading: leaguesLoading,
  } = useApiQuery(["leagues-dropdown"], () => api.getLeagues({ is_active: true }));

  const leagues = leaguesData?.data ?? [];

  const activeData = selectedDatePreset === "today" ? todayData : upcomingData;
  const activeLoading = selectedDatePreset === "today" ? todayLoading : upcomingLoading;
  const activeMatches: MatchBrief[] = activeData?.data ?? [];

  const onRefresh = () => {
    refetchToday();
    refetchUpcoming();
    queryClient.invalidateQueries({ queryKey: ["leagues-dropdown"] });
  };

  const selectedLeagueName = leagues.find((l) => l.id === selectedLeague)?.name;

  return (
    <ScrollView
      style={[styles.container, { backgroundColor: isDark ? "#091410" : "#f7f9f7" }]}
      refreshControl={
        <RefreshControl
          refreshing={activeLoading}
          onRefresh={onRefresh}
          tintColor={isDark ? "#8bc34a" : "#0d7450"}
          colors={[isDark ? "#8bc34a" : "#0d7450"]}
        />
      }
    >
      <View style={styles.datePresets}>
        <ScrollView horizontal showsHorizontalScrollIndicator={false}>
          <View style={styles.datePresetRow}>
            {DATE_PRESETS.map((preset) => (
              <TouchableOpacity
                key={preset.value}
                style={[
                  styles.presetButton,
                  {
                    backgroundColor:
                      selectedDatePreset === preset.value
                        ? isDark
                          ? "#8bc34a"
                          : "#0d7450"
                        : isDark
                          ? "#172b23"
                          : "#eff4f1",
                  },
                ]}
                onPress={() => setSelectedDatePreset(preset.value)}
              >
                <Text
                  style={[
                    styles.presetButtonText,
                    {
                      color:
                        selectedDatePreset === preset.value
                          ? "#f7fff7"
                          : isDark
                            ? "#e7f0eb"
                            : "#121f19",
                    },
                  ]}
                >
                  {preset.label}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        </ScrollView>
      </View>

      {leaguesLoading ? null : leagues.length > 0 ? (
        <View style={styles.leagueFilter}>
          <Picker
            selectedValue={selectedLeague || ""}
            onValueChange={(value) => setSelectedLeague(value || null)}
            style={[styles.picker, { color: isDark ? "#e7f0eb" : "#121f19" }]}
            dropdownIconColor={isDark ? "#e7f0eb" : "#121f19"}
          >
            <Picker.Item label="All Leagues" value="" />
            {leagues.map((league: League) => (
              <Picker.Item key={league.id} label={league.name} value={league.id} />
            ))}
          </Picker>
        </View>
      ) : null}

      <View style={styles.sectionHeader}>
        <Text style={[styles.sectionTitle, { color: isDark ? "#e7f0eb" : "#121f19" }]}>
          {selectedDatePreset === "today" ? "Today's Matches" : "Upcoming Matches"}
        </Text>
        {selectedLeagueName && (
          <Text style={[styles.leagueTag, { color: isDark ? "#8bc34a" : "#0d7450" }]}>
            {selectedLeagueName}
          </Text>
        )}
      </View>

      {activeLoading ? (
        <LoadingState />
      ) : activeMatches.length === 0 ? (
        <EmptyState
          title="No matches found"
          description={
            selectedLeague
              ? `No upcoming matches for ${selectedLeagueName}`
              : "No matches found for the selected period"
          }
        />
      ) : (
        activeMatches.map((match: MatchBrief) => (
          <MatchCard key={match.id} match={match} size="normal" />
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
  datePresets: {
    paddingBottom: 12,
  },
  datePresetRow: {
    flexDirection: "row",
    gap: 8,
    paddingHorizontal: 16,
  },
  presetButton: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 999,
  },
  presetButtonText: {
    fontSize: 13,
    fontWeight: "600",
  },
  leagueFilter: {
    marginHorizontal: 16,
    marginBottom: 16,
    borderRadius: 12,
    overflow: "hidden",
    borderWidth: 1,
    borderColor: "rgba(128,128,128,0.2)",
  },
  picker: {
    height: 44,
  },
  sectionHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    paddingHorizontal: 16,
    marginBottom: 12,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: "700",
  },
  leagueTag: {
    fontSize: 12,
    fontWeight: "600",
  },
});

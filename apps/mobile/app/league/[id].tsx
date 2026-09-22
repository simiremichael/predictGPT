import { useState } from "react";
import { View, ScrollView, RefreshControl, Text } from "react-native";
import { useLocalSearchParams } from "expo-router";
import { useTheme } from "@/lib/theme/provider";
import { api } from "@/lib/api/client";
import { LoadingState } from "@/components/common/LoadingState";
import { EmptyState } from "@/components/common/EmptyState";
import { useApiQuery } from "@/hooks/useApiQuery";
import { useQueryClient } from "@tanstack/react-query";
import { getLeagueTierLabel } from "@/utils";
import type { League, Standing } from "@/types";

const TABS = [
  { id: "standings", label: "Standings" },
  { id: "fixtures", label: "Fixtures" },
  { id: "teams", label: "Teams" },
] as const;

export default function LeagueDetailScreen() {
  const { theme } = useTheme();
  const isDark = theme === "dark";
  const { id } = useLocalSearchParams<{ id: string }>();
  const queryClient = useQueryClient();

  const [activeTab, setActiveTab] = useState("standings");

  const {
    data: leagueData,
    isLoading: leagueLoading,
    refetch: refetchLeague,
    isRefetching: leagueRefetching,
  } = useApiQuery(["league-detail", id], () =>
    api.getLeague(id, {
      include_teams: activeTab === "teams",
      include_fixtures: activeTab === "fixtures",
      include_standings: activeTab === "standings",
    }),
  );

  const league: League | null = leagueData ?? null;

  const onRefresh = () => {
    refetchLeague();
  };

  if (leagueLoading) {
    return <LoadingState fullScreen />;
  }

  if (!league) {
    return (
      <EmptyState title="League not found" description="The league you're looking for doesn't exist." />
    );
  }

  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: isDark ? "#091410" : "#f7f9f7", paddingTop: 52 }}
      refreshControl={
        <RefreshControl
          refreshing={leagueRefetching}
          onRefresh={onRefresh}
          tintColor={isDark ? "#8bc34a" : "#0d7450"}
          colors={[isDark ? "#8bc34a" : "#0d7450"]}
        />
      }
    >
      <View style={{ alignItems: "center", paddingTop: 16, paddingBottom: 24, gap: 4 }}>
        <View
          style={{
            width: 64,
            height: 64,
            borderRadius: 16,
            backgroundColor: isDark ? "#172b23" : "#eff4f1",
            opacity: 0.7,
          }}
        />
        <Text
          style={{ fontSize: 24, fontWeight: "800", marginTop: 8, color: isDark ? "#e7f0eb" : "#121f19" }}
        >
          {league.name}
        </Text>
        {league.country && (
          <Text style={{ fontSize: 14, color: isDark ? "#9eb1a4" : "#617068" }}>{league.country}</Text>
        )}
        {league.tier && (
          <Text style={{ fontSize: 12, color: isDark ? "#9eb1a4" : "#617068" }}>
            {getLeagueTierLabel(league.tier)}
          </Text>
        )}
      </View>

      <View style={{ flexDirection: "row", borderBottomWidth: 1, borderColor: isDark ? "#253e33" : "#dce6e0" }}>
        {TABS.map((tab) => (
          <TouchableOpacity
            key={tab.id}
            style={{
              paddingVertical: 12,
              marginRight: 24,
              borderBottomWidth: 2,
              borderBottomColor:
                activeTab === tab.id
                  ? isDark
                    ? "#8bc34a"
                    : "#0d7450"
                  : "transparent",
            }}
            onPress={() => setActiveTab(tab.id)}
          >
            <Text
              style={{
                fontSize: 14,
                fontWeight: activeTab === tab.id ? "700" : "500",
                color: activeTab === tab.id ? (isDark ? "#8bc34a" : "#0d7450") : isDark ? "#9eb1a4" : "#617068",
              }}
            >
              {tab.label}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      <View style={{ paddingHorizontal: 16, paddingBottom: 24, gap: 16 }}>
        {activeTab === "standings" && league.standings_summary && league.standings_summary.length > 0 && (
          <>
            <View
              style={{
                flexDirection: "row",
                alignItems: "center",
                justifyContent: "space-between",
                paddingVertical: 10,
                borderBottomWidth: 1,
                borderBottomColor: isDark ? "#253e33" : "#dce6e0",
              }}
            >
              <Text style={{ fontSize: 11, fontWeight: "700", color: isDark ? "#9eb1a4" : "#617068", width: 24 }}>
                #
              </Text>
              <Text style={{ fontSize: 11, fontWeight: "700", color: isDark ? "#9eb1a4" : "#617068", flex: 1, marginLeft: 4 }}>
                Team
              </Text>
              <Text style={{ fontSize: 11, fontWeight: "700", color: isDark ? "#9eb1a4" : "#617068", width: 20, textAlign: "center" }}>
                P
              </Text>
              <Text style={{ fontSize: 11, fontWeight: "700", color: isDark ? "#9eb1a4" : "#617068", width: 20, textAlign: "center" }}>
                W
              </Text>
              <Text style={{ fontSize: 11, fontWeight: "700", color: isDark ? "#9eb1a4" : "#617068", width: 20, textAlign: "center" }}>
                D
              </Text>
              <Text style={{ fontSize: 11, fontWeight: "700", color: isDark ? "#9eb1a4" : "#617068", width: 20, textAlign: "center" }}>
                L
              </Text>
              <Text style={{ fontSize: 11, fontWeight: "700", color: isDark ? "#9eb1a4" : "#617068", width: 30, textAlign: "center" }}>
                Pts
              </Text>
              <Text style={{ fontSize: 11, fontWeight: "700", color: isDark ? "#9eb1a4" : "#617068", width: 30, textAlign: "center" }}>
                GD
              </Text>
            </View>
            {league.standings_summary.map((standing: Standing) => (
              <View
                key={standing.team_id}
                style={{
                  flexDirection: "row",
                  alignItems: "center",
                  justifyContent: "space-between",
                  paddingVertical: 8,
                  borderBottomWidth: 1,
                  borderBottomColor: isDark ? "#253e33" : "#dce6e0",
                }}
              >
                <Text style={{ fontSize: 12, fontWeight: "600", color: isDark ? "#9eb1a4" : "#617068", width: 24 }}>
                  {standing.position}
                </Text>
                <Text style={{ fontSize: 13, fontWeight: "600", color: isDark ? "#e7f0eb" : "#121f19", flex: 1, marginLeft: 4 }} numberOfLines={1}>
                  {standing.team_name}
                </Text>
                <Text style={{ fontSize: 12, color: isDark ? "#9eb1a4" : "#617068", width: 20, textAlign: "center" }}>
                  {standing.played}
                </Text>
                <Text style={{ fontSize: 12, color: isDark ? "#9eb1a4" : "#617068", width: 20, textAlign: "center" }}>
                  {standing.wins}
                </Text>
                <Text style={{ fontSize: 12, color: isDark ? "#9eb1a4" : "#617068", width: 20, textAlign: "center" }}>
                  {standing.draws}
                </Text>
                <Text style={{ fontSize: 12, color: isDark ? "#9eb1a4" : "#617068", width: 20, textAlign: "center" }}>
                  {standing.losses}
                </Text>
                <Text style={{ fontSize: 12, fontWeight: "700", color: isDark ? "#e7f0eb" : "#121f19", width: 30, textAlign: "center" }}>
                  {standing.points}
                </Text>
                <Text style={{ fontSize: 12, color: isDark ? "#9eb1a4" : "#617068", width: 30, textAlign: "center" }}>
                  {standing.goal_difference}
                </Text>
              </View>
            ))}
          </>
        )}

        {activeTab === "fixtures" && (
          <EmptyState title="Fixtures" description="Fixture data will appear here when available" />
        )}

        {activeTab === "teams" && (!league.standings_summary || league.standings_summary.length === 0) && (
          <EmptyState title="Teams" description="Team data will appear here when available" />
        )}
      </View>
    </ScrollView>
  );
}

import React from "react";
import { StyleSheet, Text, View, TouchableOpacity, ViewStyle } from "react-native";
import { Link } from "expo-router";
import { useTheme } from "@/lib/theme/provider";
import type { League } from "@/types";

interface LeagueCardProps {
  league: League;
  size?: "compact" | "normal";
  style?: ViewStyle;
}

export function LeagueCard({ league, size = "normal", style }: LeagueCardProps) {
  const { theme } = useTheme();
  const isDark = theme === "dark";
  const isCompact = size === "compact";
  const teamCount = league.team_count ?? league.standings_summary?.length;

  return (
    <Link href={`/league/${league.id}`} asChild>
      <TouchableOpacity
        style={[
          isCompact ? styles.compactCard : styles.card,
          {
            backgroundColor: isDark ? "#0f1f19" : "#ffffff",
            borderColor: isDark ? "#253e33" : "#dce6e0",
          },
          style,
        ]}
        activeOpacity={0.7}
      >
        {isCompact ? (
          <View style={styles.compactContent}>
            <View
              style={[
                styles.logoPlaceholder,
                { backgroundColor: isDark ? "#172b23" : "#eff4f1" },
              ]}
            />
            <Text
              style={[styles.compactName, { color: isDark ? "#e7f0eb" : "#121f19" }]}
              numberOfLines={2}
            >
              {league.name}
            </Text>
            {league.country && (
              <Text
                style={[styles.country, { color: isDark ? "#9eb1a4" : "#617068" }]}
                numberOfLines={1}
              >
                {league.country}
              </Text>
            )}
          </View>
        ) : (
          <View style={styles.content}>
            <View
              style={[
                styles.logoPlaceholder,
                { backgroundColor: isDark ? "#172b23" : "#eff4f1" },
              ]}
            />
            <View style={styles.info}>
              <Text
                style={[styles.name, { color: isDark ? "#e7f0eb" : "#121f19" }]}
                numberOfLines={1}
              >
                {league.name}
              </Text>
              {league.country && (
                <Text style={[styles.country, { color: isDark ? "#9eb1a4" : "#617068" }]}>
                  {league.country}
                </Text>
              )}
              {teamCount !== undefined && teamCount > 0 && (
                <Text style={[styles.teamCount, { color: isDark ? "#9eb1a4" : "#617068" }]}>
                  {teamCount} teams
                </Text>
              )}
            </View>
          </View>
        )}
      </TouchableOpacity>
    </Link>
  );
}

const styles = StyleSheet.create({
  card: {
    borderRadius: 16,
    borderWidth: 1,
    padding: 14,
    width: 160,
    alignItems: "center",
    gap: 8,
  },
  compactCard: {
    borderRadius: 12,
    borderWidth: 1,
    padding: 10,
    width: 120,
    alignItems: "center",
    gap: 6,
  },
  content: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  compactContent: {
    alignItems: "center",
    gap: 4,
  },
  logoPlaceholder: {
    width: 40,
    height: 40,
    borderRadius: 8,
    opacity: 0.7,
  },
  info: {
    flex: 1,
    alignItems: "center",
  },
  name: {
    fontSize: 13,
    fontWeight: "700",
    textAlign: "center",
  },
  compactName: {
    fontSize: 11,
    fontWeight: "700",
    textAlign: "center",
  },
  country: {
    fontSize: 11,
    opacity: 0.8,
  },
  teamCount: {
    fontSize: 10,
  },
});

import React from "react";
import { StyleSheet, Text, View, ScrollView, TouchableOpacity, Switch, Alert } from "react-native";
import { Link } from "expo-router";
import { useTheme } from "@/lib/theme/provider";
import { api } from "@/lib/api/client";
import { LoadingState } from "@/components/common/LoadingState";
import { useApiQuery } from "@/hooks/useApiQuery";
import { clearCache } from "@/lib/storage";
import type { PredictionStats } from "@/types";

export default function ProfileScreen() {
  const { theme, setThemeMode } = useTheme();
  const isDark = theme === "dark";

  const { data: statsData, isLoading: statsLoading } = useApiQuery(["prediction-stats"], () =>
    api.getPredictionStats(),
  );

  const stats: PredictionStats | null = statsData ?? null;

  const toggleTheme = (value: boolean) => {
    setThemeMode(value ? "dark" : "light");
  };

  const exportCache = async () => {
    Alert.alert("Cache Export", "Cache data would be exported in production");
  };

  const handleClearCache = async () => {
    await clearCache();
    Alert.alert("Cache Cleared", "Local cache has been cleared.");
  };

  if (statsLoading) {
    return <LoadingState fullScreen />;
  }

  return (
    <ScrollView
      style={[styles.container, { backgroundColor: isDark ? "#091410" : "#f7f9f7" }]}
    >
      <View style={styles.header}>
        <Text style={[styles.title, { color: isDark ? "#e7f0eb" : "#121f19" }]}>
          Profile
        </Text>
      </View>

      <View
        style={[
          styles.section,
          {
            backgroundColor: isDark ? "#0f1f19" : "#ffffff",
            borderColor: isDark ? "#253e33" : "#dce6e0",
          },
        ]}
      >
        <Text style={[styles.sectionTitle, { color: isDark ? "#e7f0eb" : "#121f19" }]}>
          Appearance
        </Text>
        <View style={styles.settingRow}>
          <Text style={[styles.settingLabel, { color: isDark ? "#e7f0eb" : "#121f19" }]}>
            Dark Mode
          </Text>
          <Switch
            value={isDark}
            onValueChange={toggleTheme}
            trackColor={{ false: "#9eb1a4", true: isDark ? "#8bc34a" : "#0d7450" }}
            thumbColor={isDark ? "#091410" : "#f7fff7"}
          />
        </View>
      </View>

      <View
        style={[
          styles.section,
          {
            backgroundColor: isDark ? "#0f1f19" : "#ffffff",
            borderColor: isDark ? "#253e33" : "#dce6e0",
          },
        ]}
      >
        <Text style={[styles.sectionTitle, { color: isDark ? "#e7f0eb" : "#121f19" }]}>
          Prediction Stats
        </Text>
        {stats && (
          <View style={styles.statsGrid}>
            <View style={styles.statItem}>
              <Text style={[styles.statValue, { color: isDark ? "#e7f0eb" : "#121f19" }]}>
                {stats.total_predictions}
              </Text>
              <Text style={[styles.statLabel, { color: isDark ? "#9eb1a4" : "#617068" }]}>
                Total Predictions
              </Text>
            </View>
            {stats.last_prediction_at && (
              <View style={styles.statItem}>
                <Text style={[styles.statValue, { color: isDark ? "#e7f0eb" : "#121f19" }]}>
                  {stats.last_prediction_at}
                </Text>
                <Text style={[styles.statLabel, { color: isDark ? "#9eb1a4" : "#617068" }]}>
                  Last Prediction
                </Text>
              </View>
            )}
          </View>
        )}
      </View>

      <View
        style={[
          styles.section,
          {
            backgroundColor: isDark ? "#0f1f19" : "#ffffff",
            borderColor: isDark ? "#253e33" : "#dce6e0",
          },
        ]}
      >
        <Text style={[styles.sectionTitle, { color: isDark ? "#e7f0eb" : "#121f19" }]}>
          Data
        </Text>
        <TouchableOpacity style={styles.actionRow} onPress={exportCache}>
          <Text style={[styles.actionLabel, { color: isDark ? "#e7f0eb" : "#121f19" }]}>
            Export Cache
          </Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.actionRow} onPress={clearCache}>
          <Text style={[styles.actionLabel, { color: isDark ? "#e7f0eb" : "#121f19" }]}>
            Clear Cache
          </Text>
        </TouchableOpacity>
      </View>

      <View
        style={[
          styles.section,
          {
            backgroundColor: isDark ? "#0f1f19" : "#ffffff",
            borderColor: isDark ? "#253e33" : "#dce6e0",
          },
        ]}
      >
        <Text style={[styles.sectionTitle, { color: isDark ? "#e7f0eb" : "#121f19" }]}>
          Navigation
        </Text>
        <Link href="/methodology" asChild>
          <TouchableOpacity style={styles.navRow}>
            <Text style={[styles.actionLabel, { color: isDark ? "#e7f0eb" : "#121f19" }]}>
              Methodology
            </Text>
          </TouchableOpacity>
        </Link>
        <Link href="/performance" asChild>
          <TouchableOpacity style={styles.navRow}>
            <Text style={[styles.actionLabel, { color: isDark ? "#e7f0eb" : "#121f19" }]}>
              Model Performance
            </Text>
          </TouchableOpacity>
        </Link>
        <Link href="/search" asChild>
          <TouchableOpacity style={styles.navRow}>
            <Text style={[styles.actionLabel, { color: isDark ? "#e7f0eb" : "#121f19" }]}>
              Search
            </Text>
          </TouchableOpacity>
        </Link>
      </View>

      <View style={styles.aboutSection}>
        <Text style={[styles.aboutText, { color: isDark ? "#9eb1a4" : "#617068" }]}>
          Football AI Mobile v1.0.0
        </Text>
        <Text style={[styles.aboutText, { color: isDark ? "#9eb1a4" : "#617068" }]}>
          Statistical predictions for football matches
        </Text>
      </View>
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
    paddingBottom: 24,
  },
  title: {
    fontSize: 32,
    fontWeight: "800",
    letterSpacing: -0.5,
  },
  section: {
    marginHorizontal: 16,
    marginBottom: 16,
    borderRadius: 16,
    borderWidth: 1,
    padding: 16,
    gap: 8,
  },
  sectionTitle: {
    fontSize: 13,
    fontWeight: "800",
    textTransform: "uppercase",
    letterSpacing: 0.3,
    marginBottom: 4,
  },
  settingRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 12,
  },
  settingLabel: {
    fontSize: 15,
    fontWeight: "600",
  },
  navRow: {
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: "rgba(128,128,128,0.2)",
    marginLeft: -16,
    marginRight: -16,
  },
  statsGrid: {
    flexDirection: "row",
    justifyContent: "space-around",
    marginTop: 4,
  },
  statItem: {
    alignItems: "center",
    gap: 4,
  },
  statValue: {
    fontSize: 18,
    fontWeight: "700",
  },
  statLabel: {
    fontSize: 11,
    fontWeight: "600",
  },
  actionRow: {
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: "rgba(128,128,128,0.2)",
    marginLeft: -16,
    marginRight: -16,
  },
  actionLabel: {
    fontSize: 15,
    fontWeight: "600",
  },
  aboutSection: {
    alignItems: "center",
    paddingHorizontal: 16,
    paddingVertical: 24,
    gap: 4,
  },
  aboutText: {
    fontSize: 12,
  },
});

import React from "react";
import { StyleSheet, Text, View, ScrollView } from "react-native";
import { useTheme } from "@/lib/theme/provider";

export default function PerformanceScreen() {
  const { theme } = useTheme();
  const isDark = theme === "dark";

  return (
    <ScrollView
      style={[styles.container, { backgroundColor: isDark ? "#091410" : "#f7f9f7" }]}
    >
      <View style={styles.content}>
        <Text style={[styles.title, { color: isDark ? "#e7f0eb" : "#121f19" }]}>
          Model Performance
        </Text>

        <View style={styles.section}>
          <Text style={[styles.sectionTitle, { color: isDark ? "#e7f0eb" : "#121f19" }]}>
            Accuracy Metrics
          </Text>
          <View style={styles.metricsGrid}>
            <View
              style={[
                styles.metricCard,
                {
                  backgroundColor: isDark ? "#0f1f19" : "#ffffff",
                  borderColor: isDark ? "#253e33" : "#dce6e0",
                },
              ]}
            >
              <Text style={[styles.metricValue, { color: isDark ? "#e7f0eb" : "#121f19" }]}>
                68.4%
              </Text>
              <Text style={[styles.metricLabel, { color: isDark ? "#9eb1a4" : "#617068" }]}>
                Overall Accuracy
              </Text>
            </View>
            <View
              style={[
                styles.metricCard,
                {
                  backgroundColor: isDark ? "#0f1f19" : "#ffffff",
                  borderColor: isDark ? "#253e33" : "#dce6e0",
                },
              ]}
            >
              <Text style={[styles.metricValue, { color: isDark ? "#e7f0eb" : "#121f19" }]}>
                72.1%
              </Text>
              <Text style={[styles.metricLabel, { color: isDark ? "#9eb1a4" : "#617068" }]}>
                Top Pick Accuracy
              </Text>
            </View>
          </View>
        </View>

        <View style={styles.section}>
          <Text style={[styles.sectionTitle, { color: isDark ? "#e7f0eb" : "#121f19" }]}>
            Performance by League
          </Text>
          <View style={styles.leaguePerf}>
            <View
              style={[
                styles.leagueRow,
                { borderBottomColor: isDark ? "#253e33" : "#dce6e0" },
              ]}
            >
              <Text style={[styles.leagueName, { color: isDark ? "#e7f0eb" : "#121f19" }]}>
                Premier League
              </Text>
              <Text style={[styles.leagueAccuracy, { color: isDark ? "#8bc34a" : "#0d7450" }]}>
                69.2%
              </Text>
            </View>
            <View
              style={[
                styles.leagueRow,
                { borderBottomColor: isDark ? "#253e33" : "#dce6e0" },
              ]}
            >
              <Text style={[styles.leagueName, { color: isDark ? "#e7f0eb" : "#121f19" }]}>
                La Liga
              </Text>
              <Text style={[styles.leagueAccuracy, { color: isDark ? "#8bc34a" : "#0d7450" }]}>
                67.8%
              </Text>
            </View>
            <View
              style={[
                styles.leagueRow,
                { borderBottomColor: isDark ? "#253e33" : "#dce6e0" },
              ]}
            >
              <Text style={[styles.leagueName, { color: isDark ? "#e7f0eb" : "#121f19" }]}>
                Serie A
              </Text>
              <Text style={[styles.leagueAccuracy, { color: isDark ? "#8bc34a" : "#0d7450" }]}>
                65.3%
              </Text>
            </View>
          </View>
        </View>

        <View style={[styles.disclaimer, { backgroundColor: isDark ? "#172b23" : "#eff4f1" }]}>
          <Text style={[styles.disclaimerText, { color: isDark ? "#e7f0eb" : "#121f19" }]}>
            Performance metrics are based on historical data and may not predict future results.
            Use as reference only.
          </Text>
        </View>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  content: {
    padding: 16,
    paddingTop: 56,
    paddingBottom: 24,
  },
  title: {
    fontSize: 32,
    fontWeight: "800",
    letterSpacing: -0.5,
    marginBottom: 24,
  },
  section: {
    marginBottom: 24,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: "700",
    marginBottom: 12,
  },
  metricsGrid: {
    flexDirection: "row",
    gap: 12,
    justifyContent: "space-between",
  },
  metricCard: {
    flex: 1,
    borderRadius: 16,
    borderWidth: 1,
    padding: 16,
    alignItems: "center",
    gap: 4,
  },
  metricValue: {
    fontSize: 28,
    fontWeight: "800",
  },
  metricLabel: {
    fontSize: 12,
    fontWeight: "600",
  },
  leaguePerf: {
    borderRadius: 16,
    borderWidth: 1,
    overflow: "hidden",
  },
  leagueRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderBottomWidth: 1,
  },
  leagueName: {
    fontSize: 15,
    fontWeight: "600",
  },
  leagueAccuracy: {
    fontSize: 15,
    fontWeight: "700",
  },
  disclaimer: {
    padding: 16,
    borderRadius: 16,
    marginTop: 16,
    alignItems: "center",
  },
  disclaimerText: {
    fontSize: 12,
    lineHeight: 18,
    textAlign: "center",
  },
});

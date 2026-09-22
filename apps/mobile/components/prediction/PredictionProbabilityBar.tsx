import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { useTheme } from "@/lib/theme/provider";
import { formatProbability } from "@/utils";

interface PredictionProbabilityBarProps {
  home: number;
  draw: number;
  away: number;
  labels?: { home?: string; draw?: string; away?: string };
}

export function PredictionProbabilityBar({
  home,
  draw,
  away,
  labels = {},
}: PredictionProbabilityBarProps) {
  const { theme } = useTheme();
  const isDark = theme === "dark";

  const bars = [
    { value: home, label: labels.home || "Home", color: "#8bc34a" },
    { value: draw, label: labels.draw || "Draw", color: "#3b82f6" },
    { value: away, label: labels.away || "Away", color: "#ef4444" },
  ];

  const maxValue = Math.max(home, draw, away, 0.4);

  return (
    <View style={styles.container}>
      {bars.map((bar) => (
        <View key={bar.label} style={styles.row}>
          <Text style={[styles.label, { color: isDark ? "#9eb1a4" : "#617068", width: 50 }]}>
            {bar.label}
          </Text>
          <View
            style={[styles.barTrack, { backgroundColor: isDark ? "#172b23" : "#eff4f1" }]}
          >
            <View
              style={[
                styles.barFill,
                {
                  width: `${(bar.value / maxValue) * 100}%`,
                  backgroundColor: bar.color,
                },
              ]}
            />
          </View>
          <Text style={[styles.value, { color: isDark ? "#e7f0eb" : "#121f19", width: 50, textAlign: "right" }]}>
            {formatProbability(bar.value)}
          </Text>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: 8,
    paddingVertical: 8,
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  label: {
    fontSize: 12,
    fontWeight: "600",
  },
  barTrack: {
    flex: 1,
    height: 8,
    borderRadius: 999,
    overflow: "hidden",
  },
  barFill: {
    height: "100%",
    borderRadius: 999,
  },
  value: {
    fontSize: 12,
    fontWeight: "600",
  },
});

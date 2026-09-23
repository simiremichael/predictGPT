import React from "react";
import { StyleSheet, Text, View, ViewStyle } from "react-native";
import { useTheme } from "@/lib/theme/provider";

interface ScoreMatrixProps {
  matrix: Record<string, Record<string, number>> | null | undefined;
  maxGoals?: number;
  size?: "compact" | "normal";
  style?: ViewStyle;
}

export function ScoreMatrix({ matrix, maxGoals = 4, size = "normal", style }: ScoreMatrixProps) {
  const { theme } = useTheme();
  const isDark = theme === "dark";

  if (!matrix || Object.keys(matrix).length === 0) {
    return null;
  }

  const cellSize = size === "compact" ? 22 : 28;
  const maxValue = Object.values(matrix).reduce((max, row) => {
    if (typeof row === "object" && row !== null) {
      return Math.max(max, ...Object.values(row).filter((v) => typeof v === "number") as number[]);
    }
    return max;
  }, 0);

  const getColor = (value: number) => {
    if (!maxValue) return isDark ? "#172b23" : "#eff4f1";
    const intensity = (value / maxValue) * 0.8 + 0.2;
    const base = isDark ? "#172b23" : "#eff4f1";
    if (value > maxValue * 0.5) {
      return isDark
        ? `rgba(139, 92, 246, ${intensity})`
        : `rgba(139, 92, 246, ${intensity * 0.4})`;
    }
    return base;
  };

  const renderCell = (home: number, away: number) => {
    const value = (matrix[home] && matrix[home][away]) || 0;
    const isMostLikely =
      value ===
      Object.values(matrix).reduce((max, row) => {
        if (typeof row === "object" && row !== null) {
          return Math.max(max, ...Object.values(row).filter((v) => typeof v === "number") as number[]);
        }
        return max;
      }, 0);

    return (
      <View
        key={`${home}-${away}`}
        style={[
          styles.cell,
          {
            width: cellSize,
            height: cellSize,
            backgroundColor: getColor(value),
          },
        ]}
      >
        <Text
          style={[
            styles.cellText,
            {
              fontSize: size === "compact" ? 8 : 10,
              color: isDark ? "#e7f0eb" : "#121f19",
              fontWeight: isMostLikely && value > 0 ? "700" : "400",
            },
          ]}
        >
          {value > 0 ? `${value.toFixed(2)}` : ""}
        </Text>
      </View>
    );
  };

  const goals = Array.from({ length: maxGoals + 1 }, (_, i) => i);

  return (
    <View style={[styles.container, style]}>
      <View style={styles.header}>
        <View style={{ width: cellSize }} />
        {goals.map((g) => (
          <Text key={g} style={[styles.axisLabel, { color: isDark ? "#9eb1a4" : "#617068" }]}>
            {g}
          </Text>
        ))}
      </View>
      {goals.map((home) => (
        <View key={home} style={styles.row}>
          <Text style={[styles.axisLabel, { color: isDark ? "#9eb1a4" : "#617068" }]}>
            {home}
          </Text>
          {goals.map((away) => renderCell(home, away))}
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    alignSelf: "center",
    gap: 2,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    gap: 2,
    marginBottom: 4,
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 2,
  },
  axisLabel: {
    fontSize: 10,
    fontWeight: "600",
    width: 16,
    textAlign: "center",
  },
  cell: {
    borderRadius: 4,
    alignItems: "center",
    justifyContent: "center",
  },
  cellText: {
    textAlign: "center",
  },
});

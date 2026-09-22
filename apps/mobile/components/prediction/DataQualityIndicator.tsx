import React from "react";
import { StyleSheet, Text, View, ViewStyle } from "react-native";
import { useTheme } from "@/lib/theme/provider"; from "@/lib/theme/provider";
import { getDataQualityLabel, formatDataQuality } from "@/utils";

interface DataQualityIndicatorProps {
  quality: number | null | undefined;
  showLabel?: boolean;
  size?: "sm" | "md" | "lg";
  style?: ViewStyle;
}

export function DataQualityIndicator({
  quality,
  showLabel = true,
  size = "md",
  style,
}: DataQualityIndicatorProps) {
  const { theme } = useTheme();
  const isDark = theme === "dark";
  const label = getDataQualityLabel(quality);

  const getBarColor = () => {
    if (!quality) return isDark ? "#4b5563" : "#9ca3af";
    if (quality >= 0.8) return "#22c55e";
    if (quality >= 0.5) return "#eab308";
    return "#ef4444";
  };

  const barColor = getBarColor();
  const barWidth = quality ? `${quality * 100}%` : "0%";

  return (
    <View style={[styles.container, style]}>
      {showLabel && (
        <Text style={[styles.label, { color: isDark ? "#9eb1a4" : "#617068" }]}>
          Data Quality: {formatDataQuality(quality)} ({label})
        </Text>
      )}
      <View
        style={[
          size === "sm" ? styles.barSm : size === "lg" ? styles.barLg : styles.bar,
          { backgroundColor: isDark ? "#172b23" : "#eff4f1" },
        ]}
      >
        <View
          style={[
            size === "sm" ? styles.barFillSm : size === "lg" ? styles.barFillLg : styles.barFill,
            { backgroundColor: barColor, width: barWidth },
          ]}
        />
      </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: 4,
  },
  label: {
    fontSize: 11,
    fontWeight: "600",
  },
  bar: {
    width: "100%",
    height: 6,
    borderRadius: 999,
    overflow: "hidden",
  },
  barSm: {
    width: "100%",
    height: 4,
    borderRadius: 999,
    overflow: "hidden",
  },
  barLg: {
    width: "100%",
    height: 10,
    borderRadius: 999,
    overflow: "hidden",
  },
  barFill: {
    height: "100%",
    borderRadius: 999,
  },
  barFillSm: {
    height: "100%",
    borderRadius: 999,
  },
  barFillLg: {
    height: "100%",
    borderRadius: 999,
  },
});

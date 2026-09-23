import React from "react";
import { StyleSheet, Text, View, ViewStyle } from "react-native";
import { useTheme } from "@/lib/theme/provider";
import { formatProbability, getDataQualityLabel, formatDataQuality } from "@/utils";
import { PredictionProbabilityBar } from "./PredictionProbabilityBar";

interface PredictionCardProps {
  prediction: {
    home_probability: number;
    draw_probability: number;
    away_probability: number;
    model_confidence: number;
    top_scoreline?: { home_goals: number; away_goals: number; probability: number } | null;
    expected_goals?: { home: number; away: number } | null;
  };
  data_quality?: number | null;
  style?: ViewStyle;
  compact?: boolean;
}

export function PredictionCard({ prediction, data_quality, style, compact = false }: PredictionCardProps) {
  const { theme } = useTheme();
  const isDark = theme === "dark";

  const topPick =
    prediction.home_probability >= prediction.draw_probability &&
    prediction.home_probability >= prediction.away_probability
      ? "Home"
      : prediction.draw_probability >= prediction.away_probability
        ? "Draw"
        : "Away";

  return (
    <View
      style={[
        compact ? styles.compactCard : styles.card,
        {
          backgroundColor: isDark ? "#0f1f19" : "#ffffff",
          borderColor: isDark ? "#253e33" : "#dce6e0",
        },
        style,
      ]}
    >
      <View style={styles.header}>
        <Text style={[styles.title, { color: isDark ? "#e7f0eb" : "#121f19" }]}>
          Model Prediction
        </Text>
        {prediction.top_scoreline && (
          <Text
            style={[
              styles.predictedScore,
              { color: isDark ? "#e7f0eb" : "#121f19" },
            ]}
          >
            {prediction.top_scoreline.home_goals}-{prediction.top_scoreline.away_goals}
          </Text>
        )}
      </View>

      <View style={styles.topPickRow}>
        <View style={[styles.topPickBadge, { backgroundColor: isDark ? "#172b23" : "#eff4f1" }]}>
          <Text style={[styles.topPickText, { color: isDark ? "#e7f0eb" : "#121f19" }]}>
            Top Pick: {topPick}
          </Text>
        </View>
        <View style={[styles.confidenceBadge, { backgroundColor: isDark ? "#172b23" : "#eff4f1" }]}>
          <Text style={[styles.confidenceText, { color: isDark ? "#e7f0eb" : "#121f19" }]}>
            Confidence: {Math.round(prediction.model_confidence * 100)}%
          </Text>
        </View>
      </View>

      <PredictionProbabilityBar
        home={prediction.home_probability}
        draw={prediction.draw_probability}
        away={prediction.away_probability}
        labels={{
          home: "Home Win",
          draw: "Draw",
          away: "Away Win",
        }}
      />

      {prediction.expected_goals && (
        <View style={styles.xgRow}>
          <Text style={[styles.xgLabel, { color: isDark ? "#9eb1a4" : "#617068" }]}>
            Expected Goals
          </Text>
          <Text style={[styles.xgValue, { color: isDark ? "#e7f0eb" : "#121f19" }]}>
            {prediction.expected_goals.home.toFixed(2)} - {prediction.expected_goals.away.toFixed(2)}
          </Text>
        </View>
      )}

      {data_quality !== undefined && data_quality !== null && (
        <View style={styles.dataQualityRow}>
          <Text style={[styles.dataQualityLabel, { color: isDark ? "#9eb1a4" : "#617068" }]}>
            Data Quality
          </Text>
          <Text style={[styles.dataQualityValue, { color: isDark ? "#e7f0eb" : "#121f19" }]}>
            {formatDataQuality(data_quality)} ({getDataQualityLabel(data_quality)})
          </Text>
        </View>
      )}

      {prediction.top_scoreline && (
        <View style={styles.topScorelineDetail}>
          <Text style={[styles.topScorelineLabel, { color: isDark ? "#9eb1a4" : "#617068" }]}>
            Most Likely Scoreline
          </Text>
          <Text style={[styles.topScorelineValue, { color: isDark ? "#e7f0eb" : "#121f19" }]}>
            {prediction.top_scoreline.home_goals}-{prediction.top_scoreline.away_goals}
          </Text>
          <Text style={[styles.topScorelineProb, { color: isDark ? "#9eb1a4" : "#617068" }]}>
            ({formatProbability(prediction.top_scoreline.probability)})
          </Text>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    borderRadius: 16,
    borderWidth: 1,
    padding: 16,
    gap: 12,
  },
  compactCard: {
    borderRadius: 12,
    borderWidth: 1,
    padding: 12,
    gap: 8,
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  title: {
    fontSize: 14,
    fontWeight: "700",
    textTransform: "uppercase",
    letterSpacing: 0.3,
  },
  predictedScore: {
    fontSize: 22,
    fontWeight: "700",
  },
  topPickRow: {
    flexDirection: "row",
    gap: 8,
    flexWrap: "wrap",
  },
  topPickBadge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 999,
  },
  topPickText: {
    fontSize: 12,
    fontWeight: "600",
  },
  confidenceBadge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 999,
  },
  confidenceText: {
    fontSize: 12,
    fontWeight: "600",
  },
  xgRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: 6,
    borderBottomWidth: 1,
    borderBottomColor: "rgba(128,128,128,0.2)",
  },
  xgLabel: {
    fontSize: 12,
    fontWeight: "600",
  },
  xgValue: {
    fontSize: 12,
    fontWeight: "700",
  },
  dataQualityRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: 6,
    borderBottomWidth: 1,
    borderBottomColor: "rgba(128,128,128,0.2)",
  },
  dataQualityLabel: {
    fontSize: 12,
    fontWeight: "600",
  },
  dataQualityValue: {
    fontSize: 12,
    fontWeight: "700",
  },
  topScorelineDetail: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
  },
  topScorelineLabel: {
    fontSize: 12,
    fontWeight: "600",
  },
  topScorelineValue: {
    fontSize: 12,
    fontWeight: "700",
  },
  topScorelineProb: {
    fontSize: 12,
  },
});

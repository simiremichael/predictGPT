import { useState } from "react";
import { StyleSheet, Text, View, ScrollView, TouchableOpacity, RefreshControl } from "react-native";
import { useTheme } from "@/lib/theme/provider";
import { api } from "@/lib/api/client";
import { LoadingState } from "@/components/common/LoadingState";
import { EmptyState } from "@/components/common/EmptyState";
import { useApiQuery } from "@/hooks/useApiQuery";
import { formatDate, formatProbability } from "@/utils";
import type { PredictionHistoryItem } from "@/types";

const CONFIDENCE_FILTERS = [
  { label: "All", value: "all" },
  { label: "High (80%+)", value: "high" },
  { label: "Medium (50-79%)", value: "medium" },
  { label: "Low (<50%)", value: "low" },
];

export default function PredictionsScreen() {
  const { theme } = useTheme();
  const isDark = theme === "dark";

  const [confidenceFilter, setConfidenceFilter] = useState("all");

  const {
    data: predictionsData,
    isLoading: predictionsLoading,
    refetch: refetchPredictions,
    isRefetching: predictionsRefetching,
  } = useApiQuery(["predictions-history", confidenceFilter], () =>
    api.getPredictionHistory({ page_size: 50 }),
  );

  const predictions = predictionsData?.data ?? [];
     if (confidenceFilter === "all") return true;
     const conf = p.model_confidence;
     if (confidenceFilter === "high") return conf >= 0.8;
     if (confidenceFilter === "medium") return conf >= 0.5 && conf < 0.8;
     if (confidenceFilter === "low") return conf < 0.5;
     return true;
    });

  const onRefresh = () => {
    refetchPredictions();
  };

  if (predictionsLoading) {
    return <LoadingState fullScreen />;
  }

  return (
    <ScrollView
      style={[styles.container, { backgroundColor: isDark ? "#091410" : "#f7f9f7" }]}
      refreshControl={
        <RefreshControl
          refreshing={predictionsRefetching}
          onRefresh={onRefresh}
          tintColor={isDark ? "#8bc34a" : "#0d7450"}
          colors={[isDark ? "#8bc34a" : "#0d7450"]}
        />
      }
    >
      <View style={styles.header}>
        <Text style={[styles.title, { color: isDark ? "#e7f0eb" : "#121f19" }]}>
          Predictions
        </Text>
        <Text style={[styles.subtitle, { color: isDark ? "#9eb1a4" : "#617068" }]}>
          Historical and upcoming match predictions
        </Text>
      </View>

      <ScrollView horizontal showsHorizontalScrollIndicator={false}>
        <View style={styles.filterRow}>
          {CONFIDENCE_FILTERS.map((filter) => (
            <TouchableOpacity
              key={filter.value}
              style={[
                styles.filterButton,
                {
                  backgroundColor:
                    confidenceFilter === filter.value
                      ? isDark
                        ? "#8bc34a"
                        : "#0d7450"
                      : isDark
                        ? "#172b23"
                        : "#eff4f1",
                },
              ]}
              onPress={() => setConfidenceFilter(filter.value)}
            >
              <Text
                style={[
                  styles.filterButtonText,
                  {
                    color:
                      confidenceFilter === filter.value
                        ? "#f7fff7"
                        : isDark
                          ? "#e7f0eb"
                          : "#121f19",
                  },
                ]}
              >
                {filter.label}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
      </ScrollView>

      {filteredPredictions.length === 0 ? (
        <EmptyState
          title="No predictions found"
          description="Adjust filters or check back later for new predictions"
        />
      ) : (
        filteredPredictions.map((p: PredictionHistoryItem) => {
          const confidenceColor =
            p.model_confidence >= 0.8
              ? isDark
                ? "#22c55e"
                : "#16a34a"
              : p.model_confidence >= 0.5
                ? isDark
                  ? "#eab308"
                  : "#ca8a04"
                : isDark
                  ? "#ef4444"
                  : "#dc2626";

          return (
            <TouchableOpacity
              key={p.prediction_id}
              style={[
                styles.predictionCard,
                {
                  backgroundColor: isDark ? "#0f1f19" : "#ffffff",
                  borderColor: isDark ? "#253e33" : "#dce6e0",
                },
              ]}
              onPress={() => {
                // Navigation to prediction detail
              }}
            >
              <View style={styles.predictionHeader}>
                <Text
                  style={[styles.matchTitle, { color: isDark ? "#e7f0eb" : "#121f19" }]}
                  numberOfLines={1}
                >
                  {p.match_home_team || "Home"} vs {p.match_away_team || "Away"}
                </Text>
                <View style={[styles.confidenceBadge, { backgroundColor: isDark ? "#172b23" : "#eff4f1" }]}>
                  <Text style={[styles.confidenceText, { color: confidenceColor }]}>
                    {Math.round(p.model_confidence * 100)}%
                  </Text>
                </View>
              </View>

              <View style={styles.probabilities}>
                <View style={styles.probItem}>
                  <Text style={[styles.probLabel, { color: isDark ? "#9eb1a4" : "#617068" }]}>
                    Home
                  </Text>
                  <Text style={[styles.probValue, { color: isDark ? "#e7f0eb" : "#121f19" }]}>
                    {formatProbability(p.home_probability)}
                  </Text>
                </View>
                <View style={styles.probItem}>
                  <Text style={[styles.probLabel, { color: isDark ? "#9eb1a4" : "#617068" }]}>
                    Draw
                  </Text>
                  <Text style={[styles.probValue, { color: isDark ? "#e7f0eb" : "#121f19" }]}>
                    {formatProbability(p.draw_probability)}
                  </Text>
                </View>
                <View style={styles.probItem}>
                  <Text style={[styles.probLabel, { color: isDark ? "#9eb1a4" : "#617068" }]}>
                    Away
                  </Text>
                  <Text style={[styles.probValue, { color: isDark ? "#e7f0eb" : "#121f19" }]}>
                    {formatProbability(p.away_probability)}
                  </Text>
                </View>
              </View>

              <View style={styles.predictionFooter}>
                <Text style={[styles.modelText, { color: isDark ? "#9eb1a4" : "#617068" }]}>
                  {p.model_version || p.model_version}
                </Text>
                <Text style={[styles.dateText, { color: isDark ? "#9eb1a4" : "#617068" }]}>
                  {p.generated_at ? formatDate(p.generated_at) : "—"}
                </Text>
              </View>
            </TouchableOpacity>
          );
        })
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
  filterRow: {
    flexDirection: "row",
    gap: 8,
    paddingHorizontal: 16,
    marginBottom: 16,
  },
  filterButton: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 999,
  },
  filterButtonText: {
    fontSize: 12,
    fontWeight: "600",
  },
  predictionCard: {
    marginHorizontal: 16,
    marginBottom: 12,
    borderRadius: 16,
    borderWidth: 1,
    padding: 14,
    gap: 8,
  },
  predictionHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: 8,
  },
  matchTitle: {
    fontSize: 14,
    fontWeight: "600",
    flex: 1,
    flexShrink: 1,
  },
  confidenceBadge: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 999,
  },
  confidenceText: {
    fontSize: 12,
    fontWeight: "700",
  },
  probabilities: {
    flexDirection: "row",
    justifyContent: "space-around",
    paddingVertical: 4,
    gap: 8,
  },
  probItem: {
    alignItems: "center",
    gap: 2,
  },
  probLabel: {
    fontSize: 10,
    fontWeight: "600",
  },
  probValue: {
    fontSize: 14,
    fontWeight: "700",
  },
  predictionFooter: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginTop: 4,
  },
  modelText: {
    fontSize: 10,
    fontWeight: "600",
  },
  dateText: {
    fontSize: 11,
  },
});

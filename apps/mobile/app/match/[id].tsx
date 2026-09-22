import { useState } from "react";
import { StyleSheet, Text, View, ScrollView, TouchableOpacity, RefreshControl } from "react-native";
import { useLocalSearchParams } from "expo-router";
import { useTheme } from "@/lib/theme/provider";
import { api } from "@/lib/api/client";
import { PredictionCard } from "@/components/prediction/PredictionCard";
import { ScoreMatrix } from "@/components/prediction/ScoreMatrix";
import { EvidenceBadge } from "@/components/prediction/EvidenceBadge";
import { DataQualityIndicator } from "@/components/prediction/DataQualityIndicator";
import { LoadingState } from "@/components/common/LoadingState";
import { EmptyState } from "@/components/common/EmptyState";
import { useApiQuery } from "@/hooks/useApiQuery";
import { formatDateTime, formatScoreline, getMatchStatusLabel } from "@/utils";
import type { MatchDetail, PredictionDetail } from "@/types";

const DETAIL_TABS = [
  { id: "prediction", label: "Prediction" },
  { id: "research", label: "Research" },
  { id: "analysis", label: "Analysis" },
];

export default function MatchDetailScreen() {
  const { theme } = useTheme();
  const isDark = theme === "dark";
  const { id } = useLocalSearchParams<{ id: string }>();
  const [activeTab, setActiveTab] = useState("prediction");

  const {
    data: matchData,
    isLoading: matchLoading,
    refetch: refetchMatch,
    isRefetching: matchRefetching,
  } = useApiQuery(["match-detail", id], () => api.getMatch(id));

  const {
    data: predictionData,
    isLoading: predictionLoading,
    refetch: refetchPrediction,
  } = useApiQuery(["match-prediction", id], () => api.getMatchPrediction(id));

  const match: MatchDetail | null = matchData ?? null;
  const prediction: PredictionDetail | null = predictionData?.data ?? null;

  const onRefresh = () => {
    refetchMatch();
    refetchPrediction();
  };

  if (matchLoading) {
    return <LoadingState fullScreen />;
  }

  if (!match) {
    return (
      <EmptyState title="Match not found" description="The match you're looking for doesn't exist." />
    );
  }

  const homeTeam = match.home_team_full;
  const awayTeam = match.away_team_full;

  const predictionForCard = prediction
    ? {
        home_probability: prediction.home_probability ?? 0,
        draw_probability: prediction.draw_probability ?? 0,
        away_probability: prediction.away_probability ?? 0,
        model_confidence: prediction.confidence ?? 0,
        top_scoreline: prediction.top_scorelines?.[0] ?? null,
        expected_goals: prediction.expected_goals
          ? {
              home: prediction.expected_goals.home,
              away: prediction.expected_goals.away,
            }
          : null,
      }
    : undefined;

  return (
    <ScrollView
      style={[styles.container, { backgroundColor: isDark ? "#091410" : "#f7f9f7" }]}
      refreshControl={
        <RefreshControl
          refreshing={matchRefetching || predictionLoading}
          onRefresh={onRefresh}
          tintColor={isDark ? "#8bc34a" : "#0d7450"}
          colors={[isDark ? "#8bc34a" : "#0d7450"]}
        />
      }
    >
      <View style={styles.matchHeader}>
        <Text style={[styles.leagueName, { color: isDark ? "#9eb1a4" : "#617068" }]}>
          {match.league_name || "Unknown League"}
        </Text>
        <View
          style={[
            styles.statusBadge,
            { backgroundColor: isDark ? "#172b23" : "#eff4f1" },
          ]}
        >
          <Text
            style={[
              styles.statusText,
              {
                color:
                  match.status === "live"
                    ? isDark
                      ? "#f87171"
                      : "#dc2626"
                    : isDark
                      ? "#9eb1a4"
                      : "#617068",
              },
            ]}
          >
            {getMatchStatusLabel(match.status)}
          </Text>
        </View>
      </View>

      <View style={styles.teamsSection}>
        <View style={styles.teamSection}>
          {homeTeam?.logo_url && (
            <View style={[styles.logoPlaceholder, { backgroundColor: isDark ? "#172b23" : "#eff4f1" }]}>
              <Text style={{ fontSize: 14, color: isDark ? "#9eb1a4" : "#617068" }}>
                {homeTeam.short_name?.[0] ?? homeTeam.name?.[0] ?? "H"}
              </Text>
            </View>
          )}
          <Text style={[styles.teamName, { color: isDark ? "#e7f0eb" : "#121f19" }]} numberOfLines={1}>
            {match.home_team_name || homeTeam?.name || "Home"}
          </Text>
          {match.home_score !== null && match.is_finished && (
            <Text style={[styles.teamScore, { color: isDark ? "#e7f0eb" : "#121f19" }]}>
              {match.home_score}
            </Text>
          )}
        </View>

        <View style={styles.scoreArea}>
          <Text style={[styles.matchDate, { color: isDark ? "#9eb1a4" : "#617068" }]}>
            {match.kickoff_at ? formatDateTime(match.kickoff_at) : "Date TBA"}
          </Text>
          {match.venue && (
            <Text style={[styles.venue, { color: isDark ? "#9eb1a4" : "#617068" }]}>
              {match.venue}
            </Text>
          )}
          {!match.is_finished && match.home_score === null && match.away_score === null && (
            <Text style={[styles.vs, { color: isDark ? "#9eb1a4" : "#617068" }]}>VS</Text>
          )}
          {match.home_score !== null && match.away_score !== null && (
            <Text style={[styles.finalScore, { color: isDark ? "#e7f0eb" : "#121f19" }]}>
              {formatScoreline(match.home_score, match.away_score)}
            </Text>
          )}
        </View>

        <View style={styles.teamSection}>
          {awayTeam?.logo_url && (
            <View style={[styles.logoPlaceholder, { backgroundColor: isDark ? "#172b23" : "#eff4f1" }]}>
              <Text style={{ fontSize: 14, color: isDark ? "#9eb1a4" : "#617068" }}>
                {awayTeam.short_name?.[0] ?? awayTeam.name?.[0] ?? "A"}
              </Text>
            </View>
          )}
          <Text style={[styles.teamName, { color: isDark ? "#e7f0eb" : "#121f19" }]} numberOfLines={1}>
            {match.away_team_name || awayTeam?.name || "Away"}
          </Text>
          {match.away_score !== null && match.is_finished && (
            <Text style={[styles.teamScore, { color: isDark ? "#e7f0eb" : "#121f19" }]}>
              {match.away_score}
            </Text>
          )}
        </View>
      </View>

      <View style={styles.tabContainer}>
        {DETAIL_TABS.map((tab) => (
          <TouchableOpacity
            key={tab.id}
            style={[
              styles.tab,
              {
                borderBottomColor:
                  activeTab === tab.id
                    ? isDark
                      ? "#8bc34a"
                      : "#0d7450"
                    : "transparent",
              },
            ]}
            onPress={() => setActiveTab(tab.id)}
          >
            <Text
              style={[
                styles.tabText,
                {
                  color:
                    activeTab === tab.id
                      ? isDark
                        ? "#8bc34a"
                        : "#0d7450"
                      : isDark
                        ? "#9eb1a4"
                        : "#617068",
                  fontWeight: activeTab === tab.id ? "700" : "500",
                },
              ]}
            >
              {tab.label}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {activeTab === "prediction" && (
        <View style={styles.tabContent}>
          {predictionLoading ? (
            <LoadingState />
          ) : prediction ? (
            <>
              {predictionForCard && (
                <PredictionCard
                  prediction={predictionForCard}
                  data_quality={prediction.research?.data_quality ?? null}
                />
              )}

              {prediction.score_matrix && (
                <View
                  style={[
                    styles.matrixContainer,
                    { backgroundColor: isDark ? "#0f1f19" : "#ffffff" },
                  ]}
                >
                  <Text style={[styles.matrixTitle, { color: isDark ? "#e7f0eb" : "#121f19" }]}>
                    Score Matrix
                  </Text>
                  <ScoreMatrix matrix={prediction.score_matrix} />
                </View>
              )}

              {prediction.research && prediction.research.available && (
                <View
                  style={[
                    styles.researchContainer,
                    { backgroundColor: isDark ? "#0f1f19" : "#ffffff" },
                  ]}
                >
                  <Text style={[styles.researchTitle, { color: isDark ? "#e7f0eb" : "#121f19" }]}>
                    Research Evidence
                  </Text>
                  {(prediction.research.injuries_count > 0 ||
                    prediction.research.suspensions_count > 0 ||
                    prediction.research.team_news_count > 0) && (
                    <View style={styles.evidenceContainer}>
                      {prediction.research.injuries_count > 0 && (
                        <EvidenceBadge
                          status="reported"
                          subject={`Injuries (${prediction.research.injuries_count})`}
                        />
                      )}
                      {prediction.research.suspensions_count > 0 && (
                        <EvidenceBadge
                          status="reported"
                          subject={`Suspensions (${prediction.research.suspensions_count})`}
                        />
                      )}
                      {prediction.research.team_news_count > 0 && (
                        <EvidenceBadge
                          status="reported"
                          subject={`Team News (${prediction.research.team_news_count})`}
                        />
                      )}
                    </View>
                  )}
                  <DataQualityIndicator
                    quality={prediction.research.data_quality}
                    style={{ marginTop: 8 }}
                  />
                </View>
              )}

              {prediction.ai_explanation && (
                <View
                  style={[
                    styles.explanationContainer,
                    { backgroundColor: isDark ? "#0f1f19" : "#ffffff" },
                  ]}
                >
                  <Text style={[styles.explanationTitle, { color: isDark ? "#e7f0eb" : "#121f19" }]}>
                    Statistical Outlook
                  </Text>
                  <Text style={[styles.explanationText, { color: isDark ? "#9eb1a4" : "#617068" }]}>
                    {prediction.ai_explanation}
                  </Text>
                </View>
              )}
            </>
          ) : (
            <EmptyState title="No prediction available" description="Prediction will be generated after data is collected" />
          )}
        </View>
      )}

      {activeTab === "research" && (
        <View style={styles.tabContent}>
          {prediction?.research ? (
            <View
              style={{
                backgroundColor: isDark ? "#0f1f19" : "#ffffff",
                borderRadius: 16,
                borderWidth: 1,
                borderColor: isDark ? "#253e33" : "#dce6e0",
                padding: 16,
                gap: 12,
              }}
            >
              <Text style={[styles.researchTitle, { color: isDark ? "#e7f0eb" : "#121f19" }]}>
                Research Data
              </Text>
              <View style={{ gap: 8 }}>
                <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
                  <Text style={{ color: isDark ? "#9eb1a4" : "#617068" }}>Sources</Text>
                  <Text style={{ color: isDark ? "#e7f0eb" : "#121f19", fontWeight: "600" }}>
                    {prediction.research.sources_count}
                  </Text>
                </View>
                <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
                  <Text style={{ color: isDark ? "#9eb1a4" : "#617068" }}>Injuries</Text>
                  <Text style={{ color: isDark ? "#e7f0eb" : "#121f19", fontWeight: "600" }}>
                    {prediction.research.injuries_count}
                  </Text>
                </View>
                <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
                  <Text style={{ color: isDark ? "#9eb1a4" : "#617068" }}>Suspensions</Text>
                  <Text style={{ color: isDark ? "#e7f0eb" : "#121f19", fontWeight: "600" }}>
                    {prediction.research.suspensions_count}
                  </Text>
                </View>
                <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
                  <Text style={{ color: isDark ? "#9eb1a4" : "#617068" }}>Team News</Text>
                  <Text style={{ color: isDark ? "#e7f0eb" : "#121f19", fontWeight: "600" }}>
                    {prediction.research.team_news_count}
                  </Text>
                </View>
                <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
                  <Text style={{ color: isDark ? "#9eb1a4" : "#617068" }}>Conflicts</Text>
                  <Text style={{ color: isDark ? "#e7f0eb" : "#121f19", fontWeight: "600" }}>
                    {prediction.research.conflicts_count}
                  </Text>
                </View>
                <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
                  <Text style={{ color: isDark ? "#9eb1a4" : "#617068" }}>Avg Credibility</Text>
                  <Text style={{ color: isDark ? "#e7f0eb" : "#121f19", fontWeight: "600" }}>
                    {Math.round(prediction.research.average_credibility * 100)}%
                  </Text>
                </View>
                <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
                  <Text style={{ color: isDark ? "#9eb1a4" : "#617068" }}>Avg Freshness</Text>
                  <Text style={{ color: isDark ? "#e7f0eb" : "#121f19", fontWeight: "600" }}>
                    {Math.round(prediction.research.average_freshness * 100)}%
                  </Text>
                </View>
              </View>
            </View>
          ) : (
            <EmptyState title="No research data" description="Research data is not available for this match" />
          )}
        </View>
      )}

      {activeTab === "analysis" && (
        <View style={styles.tabContent}>
          {prediction?.statistics && typeof prediction.statistics === "object" && Object.keys(prediction.statistics).length > 0 ? (
            <View
              style={{
                backgroundColor: isDark ? "#0f1f19" : "#ffffff",
                borderRadius: 16,
                borderWidth: 1,
                borderColor: isDark ? "#253e33" : "#dce6e0",
                padding: 16,
                gap: 12,
              }}
            >
              <Text style={[styles.researchTitle, { color: isDark ? "#e7f0eb" : "#121f19" }]}>
                Match Statistics
              </Text>
              {Object.entries(prediction.statistics).map(([key, value]) => (
                <View key={key} style={{ flexDirection: "row", justifyContent: "space-between" }}>
                  <Text style={{ color: isDark ? "#9eb1a4" : "#617068", textTransform: "capitalize" }}>
                    {key.replace(/_/g, " ")}
                  </Text>
                  <Text style={{ color: isDark ? "#e7f0eb" : "#121f19", fontWeight: "600" }}>
                    {typeof value === "number" ? value.toFixed(2) : String(value ?? "-")}
                  </Text>
                </View>
              ))}
            </View>
          ) : (
            <EmptyState title="No statistics available" description="Statistics will appear here after the match" />
          )}
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  matchHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: 16,
    paddingTop: 56,
    paddingBottom: 12,
  },
  leagueName: {
    fontSize: 12,
    fontWeight: "700",
    textTransform: "uppercase",
    letterSpacing: 0.3,
  },
  statusBadge: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 999,
  },
  statusText: {
    fontSize: 11,
    fontWeight: "600",
  },
  teamsSection: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 24,
    paddingVertical: 16,
    gap: 8,
  },
  teamSection: {
    alignItems: "center",
    gap: 6,
  },
  teamName: {
    fontSize: 16,
    fontWeight: "700",
    textAlign: "center",
  },
  teamScore: {
    fontSize: 24,
    fontWeight: "700",
  },
  scoreArea: {
    alignItems: "center",
    gap: 4,
  },
  matchDate: {
    fontSize: 12,
    fontWeight: "600",
  },
  venue: {
    fontSize: 11,
  },
  vs: {
    fontSize: 14,
    fontWeight: "600",
  },
  finalScore: {
    fontSize: 20,
    fontWeight: "700",
  },
  tabContainer: {
    flexDirection: "row",
    borderBottomWidth: 1,
    borderColor: "rgba(128,128,128,0.2)",
    paddingHorizontal: 16,
  },
  tab: {
    paddingVertical: 12,
    marginRight: 24,
    borderBottomWidth: 2,
  },
  tabText: {
    fontSize: 14,
  },
  tabContent: {
    paddingHorizontal: 16,
    gap: 16,
    paddingBottom: 24,
  },
  matrixContainer: {
    borderRadius: 16,
    borderWidth: 1,
    padding: 16,
  },
  matrixTitle: {
    fontSize: 14,
    fontWeight: "700",
    marginBottom: 8,
    textAlign: "center",
  },
  researchContainer: {
    borderRadius: 16,
    borderWidth: 1,
    padding: 16,
    gap: 12,
  },
  researchTitle: {
    fontSize: 14,
    fontWeight: "700",
    marginBottom: 4,
  },
  evidenceContainer: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 6,
  },
  explanationContainer: {
    borderRadius: 16,
    borderWidth: 1,
    padding: 16,
  },
  explanationTitle: {
    fontSize: 14,
    fontWeight: "700",
    marginBottom: 8,
  },
  explanationText: {
    fontSize: 13,
    lineHeight: 18,
  },
  logoPlaceholder: {
    width: 48,
    height: 48,
    borderRadius: 8,
    alignItems: "center",
    justifyContent: "center",
  },
});

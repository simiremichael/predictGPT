import { StyleSheet, Text, View, TouchableOpacity, ViewStyle } from "react-native";
import { Link } from "expo-router";
import { useTheme } from "@/lib/theme/provider";
import { TeamLogo } from "@/components/common/TeamLogo";
import { getMatchStatusLabel, formatTime, formatProbability } from "@/utils";
import type { MatchBrief } from "@/types";

interface MatchCardProps {
  match: MatchBrief;
  homeLogoUrl?: string | null;
  awayLogoUrl?: string | null;
  prediction?: {
    home_probability: number;
    draw_probability: number;
    away_probability: number;
    model_confidence: number;
    top_scoreline?: { home_goals: number; away_goals: number; probability: number };
  };
  showPrediction?: boolean;
  size?: "compact" | "normal" | "large";
  style?: ViewStyle;
  onPress?: (match: MatchBrief) => void;
}

export function MatchCard({
  match,
  homeLogoUrl,
  awayLogoUrl,
  prediction,
  showPrediction = false,
  size = "normal",
  style,
  onPress,
}: MatchCardProps) {
  const { theme } = useTheme();
  const isDark = theme === "dark";
  const isFinished = match.is_finished;

  const cardStyle = size === "compact" ? styles.compactCard : styles.card;

  const content = (
    <>
      <View style={styles.header}>
        <Text style={[styles.league, { color: isDark ? "#9eb1a4" : "#617068" }]}>
          {match.league_name || match.league_id || "Unknown League"}
        </Text>
        <View style={[styles.statusBadge, { backgroundColor: isDark ? "#172b23" : "#eff4f1" }]}>
          <Text style={[styles.statusText, { color: isDark ? "#e7f0eb" : "#121f19" }]}>
            {getMatchStatusLabel(match.status)}
          </Text>
        </View>
      </View>

      <View style={styles.teams}>
        <View style={styles.team}>
          <TeamLogo uri={homeLogoUrl} size={size === "compact" ? 24 : 32} />
          <Text
            style={[
              styles.teamName,
              { color: isDark ? "#e7f0eb" : "#121f19", fontSize: size === "compact" ? 13 : 15 },
            ]}
            numberOfLines={1}
          >
            {match.home_team_name || "Home"}
          </Text>
        </View>

        <View style={styles.scoreContainer}>
          {isFinished && match.home_score !== null && match.away_score !== null ? (
            <Text style={[styles.score, { color: isDark ? "#e7f0eb" : "#121f19" }]}>
              {match.home_score} - {match.away_score}
            </Text>
          ) : (
            <Text style={[styles.kickoff, { color: isDark ? "#9eb1a4" : "#617068" }]}>
              {match.kickoff_at ? formatTime(match.kickoff_at) : "--:--"}
            </Text>
          )}
        </View>

        <View style={styles.team}>
          <TeamLogo uri={awayLogoUrl} size={size === "compact" ? 24 : 32} />
          <Text
            style={[
              styles.teamName,
              { color: isDark ? "#e7f0eb" : "#121f19", fontSize: size === "compact" ? 13 : 15 },
            ]}
            numberOfLines={1}
          >
            {match.away_team_name || "Away"}
          </Text>
        </View>
      </View>

      {showPrediction && prediction && (
        <View style={styles.prediction}>
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
          <View style={styles.probabilities}>
            <Text style={[styles.probText, { color: isDark ? "#9eb1a4" : "#617068" }]}>
              H: {formatProbability(prediction.home_probability)} D:{" "}
              {formatProbability(prediction.draw_probability)} A:{" "}
              {formatProbability(prediction.away_probability)}
            </Text>
          </View>
        </View>
      )}
    </>
  );

  const cardContent = (
    <TouchableOpacity
      style={[
        cardStyle,
        {
          backgroundColor: isDark ? "#0f1f19" : "#ffffff",
          borderColor: isDark ? "#253e33" : "#dce6e0",
        },
        style,
      ]}
      activeOpacity={0.7}
      onPress={() => onPress?.(match)}
    >
      {content}
    </TouchableOpacity>
  );

  return (
    <Link href={`/match/${match.id}`} asChild>
      {cardContent}
    </Link>
  );
}

const styles = StyleSheet.create({
  card: {
    borderRadius: 16,
    borderWidth: 1,
    padding: 14,
    gap: 8,
  },
  compactCard: {
    borderRadius: 12,
    borderWidth: 1,
    padding: 10,
    gap: 6,
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 8,
  },
  league: {
    fontSize: 11,
    fontWeight: "600",
    textTransform: "uppercase",
    letterSpacing: 0.3,
  },
  statusBadge: {
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 999,
  },
  statusText: {
    fontSize: 10,
    fontWeight: "600",
  },
  teams: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 12,
  },
  team: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    flex: 1,
  },
  teamName: {
    fontWeight: "600",
    flexShrink: 1,
  },
  scoreContainer: {
    minWidth: 60,
    alignItems: "center",
  },
  score: {
    fontSize: 18,
    fontWeight: "700",
  },
  kickoff: {
    fontSize: 14,
    fontWeight: "500",
  },
  prediction: {
    marginTop: 8,
    paddingTop: 8,
    borderTopWidth: 1,
    borderTopColor: "rgba(128,128,128,0.2)",
    gap: 4,
  },
  predictedScore: {
    fontSize: 16,
    fontWeight: "700",
    textAlign: "center",
  },
  probabilities: {
    flexDirection: "row",
    justifyContent: "space-around",
  },
  probText: {
    fontSize: 11,
    fontWeight: "500",
  },
});

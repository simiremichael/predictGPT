import React from "react";
import { StyleSheet, Text, View, ScrollView } from "react-native";
import { useTheme } from "@/lib/theme/provider";

export default function MethodologyScreen() {
  const { theme } = useTheme();
  const isDark = theme === "dark";

  return (
    <ScrollView
      style={[styles.container, { backgroundColor: isDark ? "#091410" : "#f7f9f7" }]}
    >
      <View style={styles.content}>
        <Text style={[styles.title, { color: isDark ? "#e7f0eb" : "#121f19" }]}>
          Methodology
        </Text>

        <View style={styles.section}>
          <Text style={[styles.sectionTitle, { color: isDark ? "#e7f0eb" : "#121f19" }]}>
            Statistical Model
          </Text>
          <Text style={[styles.body, { color: isDark ? "#9eb1a4" : "#617068" }]}>
            Our predictions are generated using a Poisson-based goal scoring model. The model estimates
            the expected goals (xG) for each team by analyzing historical match data, including attack
            and defense strength ratings, home advantage, and recent form.
          </Text>
        </View>

        <View style={styles.section}>
          <Text style={[styles.sectionTitle, { color: isDark ? "#e7f0eb" : "#121f19" }]}>
            Key Factors
          </Text>
          <View style={styles.factor}>
            <Text style={[styles.factorTitle, { color: isDark ? "#8bc34a" : "#0d7450" }]}>
              Attack & Defense Strength
            </Text>
            <Text style={[styles.body, { color: isDark ? "#9eb1a4" : "#617068" }]}>
              Each team's scoring and conceding rates are normalized against league averages to
              produce strength ratings.
            </Text>
          </View>
          <View style={styles.factor}>
            <Text style={[styles.factorTitle, { color: isDark ? "#8bc34a" : "#0d7450" }]}>
              Home Advantage
            </Text>
            <Text style={[styles.body, { color: isDark ? "#9eb1a4" : "#617068" }]}>
              The model factors in the historical home advantage for each league.
            </Text>
          </View>
          <View style={styles.factor}>
            <Text style={[styles.factorTitle, { color: isDark ? "#8bc34a" : "#0d7450" }]}>
              Recent Form
            </Text>
            <Text style={[styles.body, { color: isDark ? "#9eb1a4" : "#617068" }]}>
              Team performance is weighted by recency, with more recent matches carrying higher weight.
            </Text>
          </View>
          <View style={styles.factor}>
            <Text style={[styles.factorTitle, { color: isDark ? "#8bc34a" : "#0d7450" }]}>
              Research Data
            </Text>
            <Text style={[styles.body, { color: isDark ? "#9eb1a4" : "#617068" }]}>
              Injuries, suspensions, and team news are incorporated when available to adjust predictions.
            </Text>
          </View>
        </View>

        <View style={styles.section}>
          <Text style={[styles.sectionTitle, { color: isDark ? "#e7f0eb" : "#121f19" }]}>
            Confidence Scoring
          </Text>
          <Text style={[styles.body, { color: isDark ? "#9eb1a4" : "#617068" }]}>
            Confidence is calculated based on the gap between the top probability and the next
            highest, data quality scores, and the recency of research information. Higher confidence
            indicates greater separation between the predicted outcome and alternatives.
          </Text>
        </View>

        <View style={[styles.disclaimer, { backgroundColor: isDark ? "#172b23" : "#eff4f1" }]}>
          <Text style={[styles.disclaimerText, { color: isDark ? "#e7f0eb" : "#121f19" }]}>
            These predictions are statistical estimates, not guarantees. Always verify information
            before making decisions.
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
  body: {
    fontSize: 14,
    lineHeight: 22,
  },
  factor: {
    marginBottom: 16,
    gap: 4,
  },
  factorTitle: {
    fontSize: 14,
    fontWeight: "700",
  },
  disclaimer: {
    padding: 16,
    borderRadius: 16,
    marginTop: 16,
  },
  disclaimerText: {
    fontSize: 12,
    lineHeight: 18,
    textAlign: "center",
  },
});

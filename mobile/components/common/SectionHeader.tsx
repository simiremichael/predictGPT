import React from "react";
import { StyleSheet, Text, View, ViewStyle } from "react-native";
import { useTheme } from "@/lib/theme/provider";

interface SectionHeaderProps {
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
  kicker?: string;
}

export function SectionHeader({ title, subtitle, action, kicker }: SectionHeaderProps) {
  const { theme } = useTheme();
  const isDark = theme === "dark";

  return (
    <View style={styles.container}>
      {kicker && (
        <Text style={[styles.kicker, { color: isDark ? "#8bc34a" : "#0d7450" }]}>
          {kicker}
        </Text>
      )}
      <View style={styles.titleRow}>
        <Text style={[styles.title, { color: isDark ? "#e7f0eb" : "#121f19" }]}>
          {title}
        </Text>
        {action}
      </View>
      {subtitle && (
        <Text style={[styles.subtitle, { color: isDark ? "#9eb1a4" : "#617068" }]}>
          {subtitle}
        </Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    marginBottom: 16,
  },
  kicker: {
    fontSize: 10,
    fontWeight: "800",
    letterSpacing: 0.13,
    textTransform: "uppercase",
    marginBottom: 4,
  },
  titleRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 8,
  },
  title: {
    fontSize: 20,
    fontWeight: "700",
    letterSpacing: -0.04,
  },
  subtitle: {
    fontSize: 13,
    marginTop: 2,
  },
});

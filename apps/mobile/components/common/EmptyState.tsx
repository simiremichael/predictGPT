import React from "react";
import { StyleSheet, Text, View, ViewStyle } from "react-native";
import { useTheme } from "@/lib/theme/provider";

interface EmptyStateProps {
  title: string;
  description?: string;
  action?: React.ReactNode;
  style?: ViewStyle;
}

export function EmptyState({ title, description, action, style }: EmptyStateProps) {
  const { theme } = useTheme();
  const isDark = theme === "dark";

  return (
    <View style={[styles.container, style]}>
      <Text style={[styles.title, { color: isDark ? "#e7f0eb" : "#121f19" }]}>
        {title}
      </Text>
      {description && (
        <Text style={[styles.description, { color: isDark ? "#9eb1a4" : "#617068" }]}>
          {description}
        </Text>
      )}
      {action && <View style={styles.actionContainer}>{action}</View>}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 32,
    gap: 8,
  },
  title: {
    fontSize: 16,
    fontWeight: "600",
    textAlign: "center",
  },
  description: {
    fontSize: 13,
    textAlign: "center",
    maxWidth: "80%",
  },
  actionContainer: {
    marginTop: 12,
  },
});

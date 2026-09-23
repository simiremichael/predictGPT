import React from "react";
import { StyleSheet, Text, View, ViewStyle } from "react-native";
import { useTheme } from "@/lib/theme/provider";

interface ErrorStateProps {
  title?: string;
  message?: string;
  onRetry?: () => void;
  retryLabel?: string;
  style?: ViewStyle;
}

export function ErrorState({
  title = "Something went wrong",
  message = "Unable to load data. Please check your connection and try again.",
  onRetry,
  retryLabel = "Try Again",
  style,
}: ErrorStateProps) {
  const { theme } = useTheme();
  const isDark = theme === "dark";

  return (
    <View style={[styles.container, style]}>
      <Text style={[styles.title, { color: isDark ? "#e7f0eb" : "#121f19" }]}>
        {title}
      </Text>
      <Text style={[styles.message, { color: isDark ? "#9eb1a4" : "#617068" }]}>
        {message}
      </Text>
      {onRetry && (
        <View style={styles.buttonContainer}>
          <Text
            style={[
              styles.button,
              {
                backgroundColor: isDark ? "#8bc34a" : "#0d7450",
                color: "#f7fff7",
              },
            ]}
            onPress={onRetry}
          >
            {retryLabel}
          </Text>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 32,
    gap: 8,
    paddingHorizontal: 24,
  },
  title: {
    fontSize: 16,
    fontWeight: "600",
    textAlign: "center",
  },
  message: {
    fontSize: 13,
    textAlign: "center",
    marginTop: 4,
  },
  buttonContainer: {
    marginTop: 16,
  },
  button: {
    fontSize: 14,
    fontWeight: "600",
    paddingHorizontal: 20,
    paddingVertical: 10,
    borderRadius: 999,
  },
});

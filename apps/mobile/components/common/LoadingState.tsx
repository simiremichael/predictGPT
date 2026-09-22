import React from "react";
import { ActivityIndicator, StyleSheet, View } from "react-native";
import { useTheme } from "@/lib/theme/provider";

interface LoadingStateProps {
  message?: string;
  fullScreen?: boolean;
}

export function LoadingState({ message, fullScreen = false }: LoadingStateProps) {
  const { theme } = useTheme();
  const isDark = theme === "dark";
  const tintColor = isDark ? "#8bc34a" : "#0d7450";

  if (fullScreen) {
    return (
      <View style={[styles.fullScreen, { backgroundColor: isDark ? "#091410" : "#f7f9f7" }]}>
        <ActivityIndicator size="large" color={tintColor} />
        {message && <View style={styles.messageContainer} />}
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <ActivityIndicator size="large" color={tintColor} />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 32,
  },
  fullScreen: {
    alignItems: "center",
    justifyContent: "center",
    flex: 1,
  },
  messageContainer: {
    marginTop: 16,
  },
});

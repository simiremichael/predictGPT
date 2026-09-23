import React from "react";
import { StyleSheet, Text, View, ViewStyle } from "react-native";
import { useTheme } from "@/lib/theme/provider";
import { truncateText } from "@/utils";

interface EvidenceBadgeProps {
  status: string;
  confidence?: number | null;
  subject?: string;
  showIcon?: boolean;
  size?: "sm" | "md";
  style?: ViewStyle;
}

export function EvidenceBadge({
  status,
  confidence,
  subject,
  showIcon = true,
  size = "md",
  style,
}: EvidenceBadgeProps) {
  const { theme } = useTheme();
  const isDark = theme === "dark";

  const getColors = () => {
    const s = status.toLowerCase();
    if (s === "confirmed") return { bg: "#dcfce7", text: "#166534" };
    if (s === "reported") return { bg: " #fef3c7", text: "#92400e" };
    if (s === "speculation") return { bg: "#dbeafe", text: "#1e40af" };
    if (s === "uncertain" || s === "unverified") return { bg: "#f3f4f6", text: "#374151" };
    return { bg: "#f3f4f6", text: "#374151" };
  };

  const colors = getColors();

  if (!isDark) {
    colors.bg = colors.bg; // light defaults
  }

  const badgeText = subject
    ? `${subject}: ${status}`
    : status;

  return (
    <View
      style={[
        size === "sm" ? styles.compactBadge : styles.badge,
        { backgroundColor: colors.bg },
        style,
      ]}
    >
      {showIcon && (
        <View
          style={[
            styles.dot,
            {
              backgroundColor: colors.text,
              width: size === "sm" ? 6 : 8,
              height: size === "sm" ? 6 : 8,
            },
          ]}
        />
      )}
      <Text
        style={[
          size === "sm" ? styles.compactText : styles.text,
          { color: colors.text },
        ]}
        numberOfLines={1}
      >
        {truncateText(badgeText, size === "sm" ? 12 : 20)}
      </Text>
      {confidence !== undefined && confidence !== null && (
        <Text style={[styles.confidence, { color: colors.text, opacity: 0.8 }]}>
          {Math.round(confidence * 100)}%
        </Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 999,
  },
  compactBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 2,
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 999,
  },
  dot: {
    borderRadius: 99,
  },
  text: {
    fontSize: 11,
    fontWeight: "600",
  },
  compactText: {
    fontSize: 10,
    fontWeight: "600",
  },
  confidence: {
    fontSize: 10,
    fontWeight: "600",
    opacity: 0.8,
  },
});

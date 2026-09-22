import React, { useState } from "react";
import { Image, StyleSheet, View, ViewStyle, ImageStyle } from "react-native";
import { useTheme } from "@/lib/theme/provider";

interface TeamLogoProps {
  uri: string | null | undefined;
  size?: number;
  style?: ViewStyle | ImageStyle;
  fallback?: React.ReactNode;
}

export function TeamLogo({ uri, size = 32, style, fallback }: TeamLogoProps) {
  const { theme } = useTheme();
  const isDark = theme === "dark";
  const [hasError, setHasError] = useState(false);

  if (!uri || hasError) {
    if (fallback)
      return (
        <View style={[styles.fallback, { width: size, height: size }, fallbackContainer(size, isDark), style as ViewStyle]}>
          {fallback}
        </View>
      );
    return (
      <View
        style={[
          styles.fallback,
          { width: size, height: size },
          fallbackContainer(size, isDark),
          style as ViewStyle,
        ]}
      />
    );
  }

  return (
    <Image
      source={{ uri }}
      style={[styles.image, { width: size, height: size }, style as ImageStyle]}
      onError={() => setHasError(true)}
      resizeMode="contain"
    />
  );
}

function fallbackContainer(size: number, isDark: boolean) {
  return {
    backgroundColor: isDark ? "#172b23" : "#eff4f1",
    borderRadius: size * 0.2,
  };
}

const styles = StyleSheet.create({
  image: {
    borderRadius: 4,
  },
  fallback: {
    opacity: 0.5,
  },
});

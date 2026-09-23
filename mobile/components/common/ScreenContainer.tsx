import React from "react";
import { StyleSheet, View, ViewStyle } from "react-native";

interface ScreenContainerProps {
  children: React.ReactNode;
  style?: ViewStyle;
  withPadding?: boolean;
}

export function ScreenContainer({
  children,
  style,
  withPadding = true,
}: ScreenContainerProps) {
  return (
    <View
      style={[
        styles.container,
        withPadding && styles.padding,
        style,
      ]}
    >
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  padding: {
    paddingHorizontal: 16,
    paddingVertical: 16,
  },
});

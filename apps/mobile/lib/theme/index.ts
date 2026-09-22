import { Colors } from "./colors";

export { Colors };

export type ThemeMode = "light" | "dark" | "system";

export const themeTokens = {
  light: {
    background: "#f7f9f7",
    foreground: "#121f19",
    card: "#ffffff",
    cardForeground: "#121f19",
    primary: "#0d7450",
    primaryForeground: "#f7fff7",
    primarySoft: "#daf7ee",
    muted: "#eff4f1",
    mutedForeground: "#617068",
    border: "#dce6e0",
    input: "#eff4f1",
    secondary: "#25631b",
  },
  dark: {
    background: "#091410",
    foreground: "#e7f0eb",
    card: "#0f1f19",
    cardForeground: "#e7f0eb",
    primary: "#8bc34a",
    primaryForeground: "#f7fff7",
    primarySoft: "#0e3327",
    muted: "#172b23",
    mutedForeground: "#9eb1a4",
    border: "#253e33",
    input: "#172b23",
    secondary: "#1a3a2a",
  },
} as const;

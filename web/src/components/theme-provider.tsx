"use client";

import { ThemeProvider as TP, type ThemeProviderProps } from "next-themes";

export function ThemeProvider({ children, ...props }: ThemeProviderProps) {
  return <TP {...props}>{children}</TP>;
}

export { useTheme } from "next-themes";

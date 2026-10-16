import "expo/build/Expo.js";
import { ExpoRoot } from "expo-router";
import * as SplashScreen from "expo-splash-screen";
import { useEffect } from "react";

SplashScreen.preventAutoHideAsync();

export function App() {
  useEffect(() => {
    SplashScreen.hideAsync();
  }, []);

  const routerContext = (require as unknown as {
    context: (directory: string, recursive: boolean, filter: RegExp) => unknown;
  }).context("./", true, /\.[jt]sx?$/);
  return <ExpoRoot context={routerContext as Parameters<typeof ExpoRoot>[0]["context"]} />;
}

export default App;

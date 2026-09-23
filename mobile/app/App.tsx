import "expo/build/Expo.js";
import { ExpoRoot } from "expo-router";
import * as SplashScreen from "expo-splash-screen";
import { useEffect } from "react";

SplashScreen.preventAutoHideAsync();

export function App() {
  useEffect(() => {
    SplashScreen.hideAsync();
  }, []);

  return (
    <ExpoRoot context={require.context("./", true, /\.[jt]sx?$/)} />
  );
}

export default App;

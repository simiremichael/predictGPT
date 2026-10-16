import { Stack, SplashScreen } from "expo-router";
import { QueryProvider } from "@/lib/query/provider";
import { ThemeProvider } from "@/lib/theme/provider";
import { AuthProvider } from "@/contexts/auth";

SplashScreen.preventAutoHideAsync();

export default function RootLayout() {
  return (
    <QueryProvider>
      <ThemeProvider>
       <AuthProvider>
        <Stack
          screenOptions={{
            headerStyle: {
              backgroundColor: "transparent",
            },
            headerShadowVisible: false,
            headerTintColor: "#8bc34a",
            animation: "slide_from_right",
            contentStyle: {
              backgroundColor: "transparent",
            },
          }}
        />
       </AuthProvider>
      </ThemeProvider>
    </QueryProvider>
  );
}

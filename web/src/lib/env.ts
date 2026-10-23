interface Env {
  apiUrl: string;
  apiFallbackUrl: string;
  appName: string;
  appEnv: "development" | "production" | "staging";
  adminApiKey: string;
  flutterwavePublicKey: string;
}

export const env: Env = {
  apiUrl:
    process.env.NEXT_PUBLIC_API_URL ||
    (process.env.NODE_ENV === "development"
      ? "http://localhost:8000"
      : "https://football-ai.fastapicloud.dev"),
  apiFallbackUrl:
    process.env.NEXT_PUBLIC_API_FALLBACK_URL || "http://localhost:8000",
  appName: process.env.NEXT_PUBLIC_APP_NAME || "Football AI",
  appEnv: (process.env.NODE_ENV as Env["appEnv"]) || "development",
  adminApiKey: process.env.NEXT_PUBLIC_ADMIN_API_KEY || "",
  flutterwavePublicKey: process.env.NEXT_PUBLIC_FLUTTERWAVE_PUBLIC_KEY || "",
};

interface Env {
  apiUrl: string;
  appName: string;
  appEnv: "development" | "production" | "staging";
}

export const env: Env = {
  apiUrl: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
  appName: process.env.NEXT_PUBLIC_APP_NAME || "Football AI",
  appEnv: (process.env.NODE_ENV as Env["appEnv"]) || "development",
};

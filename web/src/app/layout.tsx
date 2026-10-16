import type { Metadata } from "next";
import "@/styles/globals.css";
import { ThemeProvider } from "@/components/theme-provider";
import { QueryProvider } from "@/components/query-provider";
import { Toaster } from "sonner";
import { ThemeToggle } from "@/components/theme-toggle";
import { Header } from "@/components/header";
import { Footer } from "@/components/footer";
import { AuthProvider } from "@/contexts/auth";

export const metadata: Metadata = {
  title: {
    default: "Football AI - AI-Powered Football Match Predictions",
    template: "%s | Football AI",
  },
  description:
    "Probabilistic football match predictions using Poisson models with optional AI research integration.",
  keywords: [
    "football",
    "soccer",
    "predictions",
    "AI",
    "Poisson",
    "machine learning",
    "sports analytics",
    "xG",
    "expected goals",
    "probabilistic",
  ],
  authors: [{ name: "Football AI" }],
  openGraph: {
    type: "website",
    locale: "en-US",
    url: "https://football-ai.app",
    siteName: "Football AI",
    title: "Football AI - AI-Powered Football Match Predictions",
    description:
      "Probabilistic football match predictions using Poisson models with optional AI research integration.",
  },
  twitter: {
    card: "summary_large_image",
    title: "Football AI - AI-Powered Football Match Predictions",
    description:
      "Probabilistic football match predictions using Poisson models with optional AI research integration.",
  },
  robots: {
    index: true,
    follow: true,
  },
};

export const viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  themeColor: {
    light: "#f4f4f2",
    dark: "#0f0f12",
  },
};

interface RootLayoutProps {
  children: React.ReactNode;
}

export default function RootLayout({ children }: RootLayoutProps) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <link rel="icon" href="/favicon.svg" type="image/svg+xml" />
      </head>
      <body className="antialiased">
        <QueryProvider>
          <AuthProvider>
          <ThemeProvider
            attribute="data-theme"
            defaultTheme="system"
            enableSystem
          >
            <div className="relative min-h-screen bg-background text-foreground">
              <div className="fixed inset-0 -z-10 bg-[radial-gradient(circle_at_top_left,rgba(16,185,129,0.10),transparent_22%),radial-gradient(circle_at_bottom_right,rgba(59,130,246,0.08),transparent_26%)]" />
              <div className="fixed inset-0 -z-10 opacity-90 [background-image:linear-gradient(rgba(148,163,184,0.04)_1px,transparent_1px),linear-gradient(90deg,rgba(148,163,184,0.04)_1px,transparent_1px)] [background-size:42px_42px]" />

              <div className="flex min-h-screen flex-1 flex-col">
                <Header />
                <main className="page-shell mx-auto flex-1 pb-8 pt-6 sm:pt-8">
                  {children}
                </main>
                <Footer />
              </div>

              <Toaster position="bottom-right" richColors closeButton />
              <ThemeToggle />
            </div>
          </ThemeProvider>
          </AuthProvider>
        </QueryProvider>
      </body>
    </html>
  );
}

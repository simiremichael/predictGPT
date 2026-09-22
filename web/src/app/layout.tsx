import type { Metadata } from "next";
import Link from "next/link";
import { BarChart3, Globe2, ShieldCheck, Trophy } from "lucide-react";
import "@/styles/globals.css";
import { ThemeProvider } from "@/components/theme-provider";
import { QueryProvider } from "@/components/query-provider";
import { Toaster } from "sonner";
import { ThemeToggle } from "@/components/theme-toggle";
import { Header } from "@/components/header";
import { Footer } from "@/components/footer";

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

const navigationGroups = [
  { href: "/leagues", label: "Leagues", icon: Trophy },
  { href: "/matches", label: "Matches", icon: Globe2 },
  { href: "/teams", label: "Teams", icon: ShieldCheck },
  { href: "/predictions", label: "Predictions", icon: BarChart3 },
];

const featuredLeagues = [
  {
    href: "/leagues/39",
    label: "Premier League",
    country: "England",
  },
  { href: "/leagues/140", label: "La Liga", country: "Spain" },
  { href: "/leagues/135", label: "Serie A", country: "Italy" },
  { href: "/leagues/78", label: "Bundesliga", country: "Germany" },
  { href: "/leagues/61", label: "Ligue 1", country: "France" },
];

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
          <ThemeProvider
            attribute="data-theme"
            defaultTheme="system"
            enableSystem
          >
            <div className="relative min-h-screen bg-background text-foreground">
              <div className="fixed inset-0 -z-10 bg-[radial-gradient(circle_at_top_left,rgba(16,185,129,0.10),transparent_22%),radial-gradient(circle_at_bottom_right,rgba(59,130,246,0.08),transparent_26%)]" />
              <div className="fixed inset-0 -z-10 opacity-90 [background-image:linear-gradient(rgba(148,163,184,0.04)_1px,transparent_1px),linear-gradient(90deg,rgba(148,163,184,0.04)_1px,transparent_1px)] [background-size:42px_42px]" />

              <div className="mx-auto flex min-h-screen max-w-[1600px] gap-4 px-2 py-2 sm:px-4 lg:gap-6 lg:px-6">
                <aside className="sticky top-4 hidden h-[calc(100vh-2rem)] w-72 shrink-0 flex-col justify-between rounded-[1.75rem] border border-border/80 bg-card/80 p-4 shadow-[0_28px_70px_rgba(15,23,42,0.08)] backdrop-blur-xl xl:flex">
                  <div>
                    <Link
                      href="/"
                      className="flex items-center gap-3 px-2 py-2"
                    >
                      <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-gradient-to-br from-primary via-emerald-500 to-cyan-500 text-lg font-black text-white shadow-[0_18px_32px_rgba(13,128,87,0.32)]">
                        FA
                      </span>
                      <div>
                        <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-muted-foreground">
                          Football intelligence
                        </p>
                        <p className="text-xl font-black tracking-[-0.06em] text-foreground">
                          Football<span className="text-primary">AI</span>
                        </p>
                      </div>
                    </Link>

                    <div className="mt-8 space-y-1">
                      {navigationGroups.map(({ href, label, icon: Icon }) => (
                        <Link
                          key={href}
                          href={href}
                          className="group flex items-center gap-3 rounded-2xl border border-transparent px-3 py-2.5 text-sm font-semibold text-muted-foreground transition-all hover:border-border hover:bg-primary/5 hover:text-foreground"
                        >
                          <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-background/80 ring-1 ring-border group-hover:bg-primary/10 group-hover:text-primary">
                            <Icon className="h-4 w-4" />
                          </span>
                          {label}
                        </Link>
                      ))}
                    </div>
                  </div>

                  <div className="rounded-[1.5rem] border border-border bg-background/60 p-3">
                    <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-muted-foreground">
                      League map
                    </p>
                    <div className="mt-3 space-y-2 text-sm text-muted-foreground">
                      {featuredLeagues.map(({ href, label, country }) => (
                        <Link
                          key={href}
                          href={href}
                          className="flex items-center justify-between rounded-xl bg-card px-2 py-1.5 text-left transition-colors hover:bg-primary/5 hover:text-primary"
                        >
                          <span>{country}</span>
                          <span className="font-semibold text-primary">
                            {label}
                          </span>
                        </Link>
                      ))}
                    </div>
                  </div>
                </aside>

                <div className="flex min-h-screen flex-1 flex-col">
                  <Header />
                  <main className="page-shell mx-auto flex-1 pb-8 pt-6 sm:pt-8">
                    {children}
                  </main>
                  <Footer />
                </div>
              </div>

              <Toaster position="bottom-right" richColors closeButton />
              <ThemeToggle />
            </div>
          </ThemeProvider>
        </QueryProvider>
      </body>
    </html>
  );
}

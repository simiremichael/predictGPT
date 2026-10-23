import type { Metadata } from "next";
import "@/styles/globals.css";
import { ThemeProvider } from "@/components/theme-provider";
import { QueryProvider } from "@/components/query-provider";
import { Toaster } from "sonner";
import { ThemeToggle } from "@/components/theme-toggle";
import { Header } from "@/components/header";
import { Footer } from "@/components/footer";
import { AuthProvider } from "@/contexts/auth";

const siteUrl = (process.env.NEXT_PUBLIC_SITE_URL || "https://football-ai.app").replace(/\/$/, "");

export const metadata: Metadata = {
  title: {
    default: "Football AI - AI-Powered Football Match Predictions",
    template: "%s | Football AI",
  },
  description:
    "Explore football match predictions, probability estimates, scorelines, team form, and research context for fixtures across major leagues.",
  metadataBase: new URL(siteUrl),
  alternates: { canonical: "/" },
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
    locale: "en_GB",
    url: siteUrl,
    siteName: "Football AI",
    title: "Football AI - AI-Powered Football Match Predictions",
    description:
      "Explore football match predictions, probability estimates, scorelines, team form, and research context for fixtures across major leagues.",
    images: [{ url: "/logo.png", width: 512, height: 512, alt: "Football AI" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "Football AI - AI-Powered Football Match Predictions",
    description:
      "Explore football match predictions, probability estimates, scorelines, team form, and research context for fixtures across major leagues.",
    images: ["/logo.png"],
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-image-preview": "large",
      "max-snippet": -1,
      "max-video-preview": -1,
    },
  },
};

export const viewport = {
  width: "device-width",
  initialScale: 1,
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
      <body className="antialiased">
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{
            __html: JSON.stringify({
              "@context": "https://schema.org",
              "@graph": [
                {
                  "@type": "Organization",
                  "@id": `${siteUrl}/#organization`,
                  name: "Football AI",
                  url: siteUrl,
                  logo: `${siteUrl}/logo.png`,
                },
                {
                  "@type": "WebSite",
                  "@id": `${siteUrl}/#website`,
                  name: "Football AI",
                  url: siteUrl,
                  publisher: { "@id": `${siteUrl}/#organization` },
                  inLanguage: "en",
                },
              ],
            }).replace(/</g, "\\u003c"),
          }}
        />
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
                <main className="page-shell mx-auto min-w-0 flex-1 pb-8 pt-5 sm:pt-8">
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

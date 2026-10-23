import type { MetadataRoute } from "next";

const siteUrl = (process.env.NEXT_PUBLIC_SITE_URL || "https://football-ai.app").replace(/\/$/, "");

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      { userAgent: "*", allow: "/", disallow: ["/admin", "/login", "/signup", "/forgot-password", "/subscription/complete", "/api/"] },
      { userAgent: "GPTBot", allow: "/", disallow: ["/admin", "/login", "/signup", "/forgot-password", "/subscription/complete", "/api/"] },
      { userAgent: "OAI-SearchBot", allow: "/", disallow: ["/admin", "/login", "/signup", "/forgot-password", "/subscription/complete", "/api/"] },
      { userAgent: "ClaudeBot", allow: "/", disallow: ["/admin", "/login", "/signup", "/forgot-password", "/subscription/complete", "/api/"] },
      { userAgent: "PerplexityBot", allow: "/", disallow: ["/admin", "/login", "/signup", "/forgot-password", "/subscription/complete", "/api/"] },
    ],
    sitemap: `${siteUrl}/sitemap.xml`,
    host: siteUrl,
  };
}

import type { MetadataRoute } from "next";

const siteUrl = (process.env.NEXT_PUBLIC_SITE_URL || "https://football-ai.app").replace(/\/$/, "");

export default function sitemap(): MetadataRoute.Sitemap {
  const lastModified = new Date();
  const publicRoutes = [
    ["", 1],
    ["/about", 0.6],
    ["/matches", 0.8],
    ["/predictions", 0.8],
    ["/results", 0.7],
    ["/leagues", 0.7],
    ["/teams", 0.7],
    ["/privacy", 0.3],
    ["/terms", 0.3],
    ["/contact", 0.4],
  ] as const;

  return publicRoutes.map(([route, priority]) => ({
    url: `${siteUrl}${route}`,
    lastModified,
    changeFrequency: route === "" ? "daily" : "weekly",
    priority,
  }));
}

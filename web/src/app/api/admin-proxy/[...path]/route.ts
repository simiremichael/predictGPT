import { NextResponse } from "next/server";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ||
  "https://football-ai.fastapicloud.dev";

const ADMIN_API_KEY =
  process.env.ADMIN_API_KEY || process.env.NEXT_PUBLIC_ADMIN_API_KEY || "";

async function proxyAdminRequest(
  request: Request,
  context: { params: Promise<{ path: string[] }> },
) {
  const { path } = await context.params;
  const target = new URL(
    `/${path.map(encodeURIComponent).join("/")}`,
    API_BASE_URL,
  );
  target.search = new URL(request.url).search;

  try {
    const response = await fetch(target, {
      method: request.method,
      headers: {
        "Content-Type": request.headers.get("content-type") || "application/json",
        "X-Admin-Api-Key": ADMIN_API_KEY,
      },
      body: ["GET", "HEAD"].includes(request.method) ? undefined : await request.text(),
      cache: "no-store",
    });

    return new NextResponse(response.body, {
      status: response.status,
      headers: {
        "Content-Type": response.headers.get("content-type") || "application/json",
      },
    });
  } catch {
    return NextResponse.json(
      {
        success: false,
        error: {
          code: "ADMIN_API_UNAVAILABLE",
          message: "The prediction service is unavailable. Please try again shortly.",
        },
      },
      { status: 503 },
    );
  }
}

export const GET = proxyAdminRequest;
export const POST = proxyAdminRequest;
export const PUT = proxyAdminRequest;
export const DELETE = proxyAdminRequest;

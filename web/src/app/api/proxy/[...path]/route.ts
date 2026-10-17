import { NextResponse } from "next/server";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ||
  "https://football-ai.fastapicloud.dev";

async function proxyApiRequest(
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
        ...(request.headers.get("authorization")
          ? { Authorization: request.headers.get("authorization")! }
          : {}),
        ...(request.headers.get("x-admin-api-key")
          ? { "X-Admin-Api-Key": request.headers.get("x-admin-api-key")! }
          : {}),
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
          code: "API_UNAVAILABLE",
          message: "The football data service is unavailable. Please try again shortly.",
        },
      },
      { status: 503 },
    );
  }
}

export const GET = proxyApiRequest;
export const POST = proxyApiRequest;
export const PUT = proxyApiRequest;
export const DELETE = proxyApiRequest;

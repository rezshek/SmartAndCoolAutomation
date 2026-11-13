import { NextRequest } from "next/server";
import { isLocalRequest } from "@/lib/local-access";

async function proxy(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  if (!isLocalRequest(request.headers)) {
    return Response.json(
      { detail: "This workspace is local only" },
      { status: 403 },
    );
  }
  const { path } = await context.params;
  if (
    !["products", "categories", "settings"].includes(path[0]) ||
    path.some((p) => p === ".." || p.includes("/"))
  ) {
    return Response.json({ detail: "Unknown endpoint" }, { status: 404 });
  }
  try {
    const body = request.method === "GET" ? undefined : await request.text();
    if (body && body.length > 100_000)
      return new Response(null, { status: 413 });
    const upstream = await fetch(
      `http://127.0.0.1:8000/api/${path.map(encodeURIComponent).join("/")}${request.nextUrl.search}`,
      {
        method: request.method,
        body,
        cache: "no-store",
        redirect: "error",
        headers: {
          "Content-Type": "application/json",
          ...(process.env.DASHBOARD_TOKEN
            ? {
                Authorization: `Bearer ${process.env.DASHBOARD_TOKEN}`,
              }
            : {}),
        },
        signal: AbortSignal.timeout(75_000),
      },
    );
    return new Response(upstream.body, {
      status: upstream.status,
      headers: {
        "Content-Type": "application/json",
        "Cache-Control": "no-store",
      },
    });
  } catch {
    return Response.json(
      {
        detail:
          "The local API is unavailable. Start FastAPI on 127.0.0.1:8000.",
      },
      { status: 503 },
    );
  }
}
export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;

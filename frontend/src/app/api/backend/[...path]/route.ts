// Generic proxy for browser-side calls into the FastAPI API contract.
//
// The browser (running inside the Replit preview iframe) cannot reach
// the API service port directly, so client components route through this
// same-origin Next.js API route, which forwards the request to the
// API process over the container's localhost network. Server
// Components fetch the API directly and
// never need this proxy.

import { NextRequest, NextResponse } from "next/server";
import { currentSession } from "@/lib/server/auth";

const BACKEND_ORIGIN =
  process.env.BACKEND_URL ||
  "http://localhost:8000";

async function proxy(req: NextRequest, path: string[]) {
  const production = process.env.NODE_ENV === "production";
  if (production && !process.env.BACKEND_URL) {
    return NextResponse.json({ detail: "Backend API is not configured." }, { status: 503 });
  }
  if (req.method !== "GET" && req.method !== "HEAD") {
    const origin = req.headers.get("origin");
    const requestUrl = new URL(req.url);
    const host = req.headers.get("host");
    const forwardedProtocol = req.headers.get("x-forwarded-proto")?.split(",", 1)[0]?.trim();
    const protocol = forwardedProtocol || requestUrl.protocol.slice(0, -1);
    const requestOrigin = host ? `${protocol}://${host}` : requestUrl.origin;
    if ((production && !origin) || (origin && origin !== requestOrigin)) {
      return NextResponse.json({ detail: "Cross-origin request rejected." }, { status: 403 });
    }
  }

  if (path[0] !== "api" || path[1] !== "v1") {
    return NextResponse.json({ detail: "Route not found." }, { status: 404 });
  }

  const session = await currentSession();
  if (production && !session) {
    return NextResponse.json({ detail: "Authentication required." }, { status: 401 });
  }
  const proxySecret = process.env.UCIF_PROXY_SECRET;
  if (production && !proxySecret) {
    return NextResponse.json({ detail: "API authentication is not configured." }, { status: 503 });
  }

  const target = `${BACKEND_ORIGIN}/${path.join("/")}${req.nextUrl.search}`;

  const headers = new Headers();
  const contentType = req.headers.get("content-type");
  const accept = req.headers.get("accept");
  const authorization = req.headers.get("authorization");
  if (contentType) headers.set("content-type", contentType);
  if (accept) headers.set("accept", accept);
  if (authorization) headers.set("authorization", authorization);
  // Never trust identity headers supplied by the browser. Production identity
  // is derived from the signed HttpOnly session by this server-side BFF.
  headers.delete("x-ucif-proxy-secret");
  headers.delete("x-ucif-user-id");
  headers.delete("x-ucif-user-role");
  if (production && session && proxySecret) {
    headers.set("x-ucif-proxy-secret", proxySecret);
    headers.set("x-ucif-user-id", session.userId);
    headers.set("x-ucif-user-role", session.role || "member");
  }

  const init: RequestInit = {
    method: req.method,
    headers,
  };

  if (req.method !== "GET" && req.method !== "HEAD") {
    init.body = await req.arrayBuffer();
  }

  try {
    const backendRes = await fetch(target, init);
    const buf = await backendRes.arrayBuffer();
    return new NextResponse(buf, {
      status: backendRes.status,
      headers: {
        "content-type": backendRes.headers.get("content-type") || "application/json",
      },
    });
  } catch {
    return NextResponse.json({ detail: "API unavailable" }, { status: 503 });
  }
}

export async function GET(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  return proxy(req, path);
}

export async function POST(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  return proxy(req, path);
}

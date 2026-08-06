// Generic proxy for browser-side calls into the FastAPI API contract.
//
// The browser (running inside the Replit preview iframe) cannot reach
// the API service port directly, so client components route through this
// same-origin Next.js API route, which forwards the request to the
// API process over the container's localhost network. Server
// Components fetch the API directly and
// never need this proxy.

import { NextRequest, NextResponse } from "next/server";

function getBackendOrigin() {
  return (
    process.env.BACKEND_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    (process.env.NODE_ENV === "production"
      ? "https://churn-framework-api.vercel.app"
      : "http://localhost:8000")
  ).replace(/\/$/, "");
}

const BACKEND_ORIGIN = getBackendOrigin();

async function proxy(req: NextRequest, path: string[]) {
  const target = `${BACKEND_ORIGIN}/${path.join("/")}${req.nextUrl.search}`;

  const headers = new Headers(req.headers);
  headers.delete("host");
  headers.delete("content-length");

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

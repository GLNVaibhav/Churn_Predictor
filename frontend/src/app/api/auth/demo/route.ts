import { NextResponse } from "next/server";
import { createDemoSession, isDemoAuthEnabled, isSameOriginRequest } from "@/lib/server/auth";

export async function POST(req: Request) {
  if (!isSameOriginRequest(req)) return NextResponse.json({ error: "Cross-origin request rejected." }, { status: 403 });
  if (!isDemoAuthEnabled()) return NextResponse.json({ error: "Demo access is not enabled." }, { status: 404 });
  try {
    const user = await createDemoSession();
    return NextResponse.json({ user });
  } catch {
    return NextResponse.json({ error: "Demo access could not be started." }, { status: 503 });
  }
}

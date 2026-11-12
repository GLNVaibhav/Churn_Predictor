import { NextResponse } from "next/server";
import { clearSession, isSameOriginRequest } from "@/lib/server/auth";

export async function POST(req: Request) {
  if (!isSameOriginRequest(req)) return NextResponse.json({ error: "Cross-origin request rejected." }, { status: 403 });
  await clearSession();
  return NextResponse.json({ ok: true });
}

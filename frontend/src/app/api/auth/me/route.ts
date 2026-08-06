import { NextResponse } from "next/server";
import { authRuntimeStatus, currentSession } from "@/lib/server/auth";

export async function GET() {
  const session = await currentSession();
  const status = await authRuntimeStatus();
  return NextResponse.json({ configured: status.ready, connected: status.connected, error: status.error, user: session });
}

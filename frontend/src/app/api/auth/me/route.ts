import { NextResponse } from "next/server";
import { authConfigStatus, authRuntimeStatus, currentSession } from "@/lib/server/auth";

export async function GET() {
  const session = await currentSession();
  if (session?.accountType === "demo") {
    const config = authConfigStatus();
    return NextResponse.json({
      configured: config.ready,
      connected: false,
      error: null,
      demoEnabled: config.demoEnabled,
      user: session,
    });
  }
  const status = await authRuntimeStatus();
  return NextResponse.json({ configured: status.ready, connected: status.connected, error: status.error, demoEnabled: status.demoEnabled, user: session });
}

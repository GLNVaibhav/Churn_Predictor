import { NextResponse } from "next/server";
import { isDemoAuthEnabled } from "@/lib/server/auth";

export async function GET() {
  return NextResponse.json({ enabled: isDemoAuthEnabled() });
}

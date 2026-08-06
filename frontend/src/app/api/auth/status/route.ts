import { NextResponse } from "next/server";
import { authRuntimeStatus } from "@/lib/server/auth";

export async function GET() {
  return NextResponse.json(await authRuntimeStatus());
}

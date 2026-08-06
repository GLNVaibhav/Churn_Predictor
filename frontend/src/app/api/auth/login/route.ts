import { NextResponse } from "next/server";
import { authConfigStatus, authErrorMessage, authenticateUser, setSession } from "@/lib/server/auth";

export async function POST(req: Request) {
  if (!authConfigStatus().ready) {
    return NextResponse.json({ error: "Authentication database is not configured." }, { status: 503 });
  }
  const body = await req.json();
  try {
    const user = await authenticateUser(String(body.email || ""), String(body.password || ""));
    await setSession(user);
    return NextResponse.json({ user });
  } catch (error) {
    return NextResponse.json({ error: authErrorMessage(error) }, { status: 401 });
  }
}

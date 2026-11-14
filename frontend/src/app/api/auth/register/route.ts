import { NextResponse } from "next/server";
import { authConfigStatus, authErrorMessage, createUser, isSameOriginRequest, setSession } from "@/lib/server/auth";

export async function POST(req: Request) {
  if (!isSameOriginRequest(req)) return NextResponse.json({ error: "Cross-origin request rejected." }, { status: 403 });
  if (!authConfigStatus().ready) {
    return NextResponse.json({ error: "Authentication database is not configured." }, { status: 503 });
  }
  const body = await req.json();
  const email = String(body.email || "");
  const password = String(body.password || "");
  const name = String(body.name || "");
  if (!email.includes("@") || password.length < 8) {
    return NextResponse.json({ error: "Enter a valid email and a password with at least 8 characters." }, { status: 400 });
  }
  let phase: "create_user" | "create_session" = "create_user";
  try {
    const user = await createUser(email, password, name);
    phase = "create_session";
    await setSession(user);
    return NextResponse.json({ user });
  } catch (error) {
    const diagnostic = error as { name?: unknown; code?: unknown; codeName?: unknown };
    console.error("[auth/register]", {
      phase,
      errorName: typeof diagnostic?.name === "string" ? diagnostic.name : "UnknownError",
      mongoCode: typeof diagnostic?.code === "number" || typeof diagnostic?.code === "string" ? diagnostic.code : undefined,
      mongoCodeName: typeof diagnostic?.codeName === "string" ? diagnostic.codeName : undefined,
    });
    return NextResponse.json({ error: authErrorMessage(error) }, { status: 400 });
  }
}

import { NextResponse } from "next/server";
import { authConfigStatus, authErrorMessage, createUser, setSession } from "@/lib/server/auth";

export async function POST(req: Request) {
  const setupToken = process.env.ADMIN_SETUP_TOKEN;
  const provided = req.headers.get("x-admin-setup-token");
  if (!setupToken || provided !== setupToken) {
    return NextResponse.json({ error: "Admin setup is not authorized." }, { status: 401 });
  }
  if (!authConfigStatus().ready) {
    return NextResponse.json({ error: "Authentication database is not configured." }, { status: 503 });
  }
  const body = await req.json();
  const email = String(body.email || "");
  const password = String(body.password || "");
  const name = String(body.name || "Admin");
  if (!email.includes("@") || password.length < 8) {
    return NextResponse.json({ error: "Enter a valid admin email and a password with at least 8 characters." }, { status: 400 });
  }
  try {
    const user = await createUser(email, password, name, "admin");
    await setSession(user);
    return NextResponse.json({ user });
  } catch (error) {
    return NextResponse.json({ error: authErrorMessage(error) }, { status: 400 });
  }
}

import "server-only";

import { cookies } from "next/headers";
import { MongoClient, ObjectId, type Db } from "mongodb";
import { createHmac, randomBytes, scryptSync, timingSafeEqual } from "crypto";

const COOKIE_NAME = "ucif_session";
const MAX_AGE_SECONDS = 60 * 60 * 24 * 7;

type SessionPayload = {
  userId: string;
  email: string;
  name: string;
  role?: "admin" | "member";
  exp: number;
};

type UserDoc = {
  _id: ObjectId;
  email: string;
  name: string;
  role?: "admin" | "member";
  passwordHash: string;
  salt: string;
  createdAt: Date;
  updatedAt: Date;
};

let clientPromise: Promise<MongoClient> | null = null;

function authSecret() {
  return process.env.AUTH_SECRET || "";
}

export function authConfigStatus() {
  return {
    database: Boolean(process.env.MONGODB_URI),
    secret: Boolean(authSecret()),
    ready: Boolean(process.env.MONGODB_URI && authSecret()),
  };
}

export async function authRuntimeStatus() {
  const config = authConfigStatus();
  if (!config.ready) {
    return { ...config, connected: false, error: null };
  }
  try {
    const db = await getDb();
    await db.command({ ping: 1 });
    return { ...config, connected: true, error: null };
  } catch (error) {
    const message = error instanceof Error ? error.message : "MongoDB connection failed";
    return { ...config, connected: false, error: message };
  }
}

export function authErrorMessage(error: unknown) {
  const message = error instanceof Error ? error.message : "Authentication failed.";
  if (message.toLowerCase().includes("bad auth")) {
    return "MongoDB rejected the configured database username or password.";
  }
  if (message.toLowerCase().includes("ssl") || message.toLowerCase().includes("network")) {
    return "MongoDB is not reachable from this deployment. Check Atlas Network Access.";
  }
  return message;
}

async function getDb(): Promise<Db> {
  const uri = process.env.MONGODB_URI;
  if (!uri) throw new Error("MongoDB is not configured");
  if (!clientPromise) {
    clientPromise = new MongoClient(uri).connect();
  }
  const client = await clientPromise;
  return client.db(process.env.MONGODB_DB || "ucif");
}

function hashPassword(password: string, salt = randomBytes(16).toString("hex")) {
  const passwordHash = scryptSync(password, salt, 64).toString("hex");
  return { salt, passwordHash };
}

function verifyPassword(password: string, user: UserDoc) {
  const attempt = Buffer.from(hashPassword(password, user.salt).passwordHash, "hex");
  const stored = Buffer.from(user.passwordHash, "hex");
  return attempt.length === stored.length && timingSafeEqual(attempt, stored);
}

function encode(value: string) {
  return Buffer.from(value).toString("base64url");
}

function decode(value: string) {
  return Buffer.from(value, "base64url").toString("utf8");
}

function sign(payload: string) {
  const secret = authSecret();
  if (!secret) throw new Error("Auth secret is not configured");
  return createHmac("sha256", secret).update(payload).digest("base64url");
}

function createToken(payload: SessionPayload) {
  const body = encode(JSON.stringify(payload));
  return `${body}.${sign(body)}`;
}

function verifyToken(token?: string): SessionPayload | null {
  if (!token || !authSecret()) return null;
  const [body, signature] = token.split(".");
  if (!body || !signature) return null;
  const expected = sign(body);
  const provided = Buffer.from(signature);
  const calculated = Buffer.from(expected);
  if (provided.length !== calculated.length || !timingSafeEqual(provided, calculated)) return null;
  const payload = JSON.parse(decode(body)) as SessionPayload;
  return payload.exp > Date.now() ? payload : null;
}

export async function createUser(email: string, password: string, name: string, role: "admin" | "member" = "member") {
  const db = await getDb();
  const normalizedEmail = email.trim().toLowerCase();
  const existing = await db.collection<UserDoc>("users").findOne({ email: normalizedEmail });
  if (existing) throw new Error("Account already exists");
  const hashed = hashPassword(password);
  const now = new Date();
  const result = await db.collection<UserDoc>("users").insertOne({
    _id: new ObjectId(),
    email: normalizedEmail,
    name: name.trim() || normalizedEmail.split("@")[0],
    role,
    ...hashed,
    createdAt: now,
    updatedAt: now,
  });
  return { userId: result.insertedId.toString(), email: normalizedEmail, name: name.trim() || normalizedEmail.split("@")[0], role };
}

export async function authenticateUser(email: string, password: string) {
  const db = await getDb();
  const user = await db.collection<UserDoc>("users").findOne({ email: email.trim().toLowerCase() });
  if (!user || !verifyPassword(password, user)) throw new Error("Invalid email or password");
  return { userId: user._id.toString(), email: user.email, name: user.name, role: user.role || "member" };
}

export async function setSession(user: { userId: string; email: string; name: string }) {
  const token = createToken({ ...user, exp: Date.now() + MAX_AGE_SECONDS * 1000 });
  const cookieStore = await cookies();
  cookieStore.set(COOKIE_NAME, token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: MAX_AGE_SECONDS,
  });
}

export async function clearSession() {
  const cookieStore = await cookies();
  cookieStore.delete(COOKIE_NAME);
}

export async function currentSession() {
  const cookieStore = await cookies();
  return verifyToken(cookieStore.get(COOKIE_NAME)?.value);
}

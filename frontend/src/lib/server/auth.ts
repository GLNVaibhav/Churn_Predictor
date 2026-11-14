import "server-only";

import { cookies } from "next/headers";
import { MongoClient, ObjectId, type Db } from "mongodb";
import { createHmac, randomBytes, scryptSync, timingSafeEqual } from "crypto";

const COOKIE_NAME = "ucif_session";
const MAX_AGE_SECONDS = 60 * 60 * 12;

type SessionPayload = {
  sid: string;
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
let indexesPromise: Promise<void> | null = null;

function authSecret() {
  return process.env.AUTH_SECRET || "";
}

export function authConfigStatus() {
  const hasStrongSecret = authSecret().length >= 32;
  return {
    database: Boolean(process.env.MONGODB_URI),
    secret: hasStrongSecret,
    ready: Boolean(process.env.MONGODB_URI && hasStrongSecret),
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
    await verifyAuthIndexes(db);
    return { ...config, connected: true, error: null };
  } catch (error) {
    return { ...config, connected: false, error: authErrorMessage(error) };
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
  if (message === "Invalid email or password") return message;
  if (message === "Account already exists") return message;
  return "Authentication request failed. Check the server configuration and try again.";
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

const REQUIRED_AUTH_INDEXES = [
  { collection: "users", key: { email: 1 }, unique: true, name: "users.email_1" },
  { collection: "sessions", key: { sid: 1 }, unique: true, name: "sessions.sid_1" },
  { collection: "sessions", key: { expiresAt: 1 }, expireAfterSeconds: 0, name: "sessions.expiresAt_1" },
] as const;

async function verifyAuthIndexes(db: Db) {
  if (!indexesPromise) {
    indexesPromise = Promise.all(REQUIRED_AUTH_INDEXES.map(async (required) => {
      const indexes = await db.collection(required.collection).listIndexes().toArray();
      const key = JSON.stringify(required.key);
      const existing = indexes.find((index) => JSON.stringify(index.key) === key);
      const requiresUnique = "unique" in required && required.unique;
      const compatible = existing
        && (requiresUnique ? existing.unique === true : existing.unique !== true)
        && existing.expireAfterSeconds === ("expireAfterSeconds" in required ? required.expireAfterSeconds : undefined)
        && !existing.sparse
        && !existing.partialFilterExpression
        && !existing.collation;
      if (!compatible) {
        throw new Error(`Authentication database index ${required.name} is missing or incompatible. Run the development index setup script.`);
      }
    })).then(() => undefined).catch((error) => {
      indexesPromise = null;
      throw error;
    });
  }
  await indexesPromise;
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
  if (secret.length < 32) throw new Error("Auth secret is not configured");
  return createHmac("sha256", secret).update(payload).digest("base64url");
}

export function constantTimeSecretEqual(expected: string, provided: string) {
  if (!expected || !provided) return false;
  const expectedBytes = Buffer.from(expected);
  const providedBytes = Buffer.from(provided);
  return expectedBytes.length === providedBytes.length && timingSafeEqual(expectedBytes, providedBytes);
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
  try {
    const payload = JSON.parse(decode(body)) as SessionPayload;
    if (!payload.sid || !payload.userId || !payload.email || !Number.isFinite(payload.exp)) return null;
    if (payload.role !== "admin" && payload.role !== "member") return null;
    return payload.exp > Date.now() ? payload : null;
  } catch {
    return null;
  }
}

export async function createUser(email: string, password: string, name: string, role: "admin" | "member" = "member") {
  const db = await getDb();
  await verifyAuthIndexes(db);
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
  }).catch((error: unknown) => {
    if ((error as { code?: unknown })?.code === 11000) throw new Error("Account already exists");
    throw error;
  });
  return { userId: result.insertedId.toString(), email: normalizedEmail, name: name.trim() || normalizedEmail.split("@")[0], role };
}

export async function authenticateUser(email: string, password: string) {
  const db = await getDb();
  await verifyAuthIndexes(db);
  const user = await db.collection<UserDoc>("users").findOne({ email: email.trim().toLowerCase() });
  if (!user || !verifyPassword(password, user)) throw new Error("Invalid email or password");
  return { userId: user._id.toString(), email: user.email, name: user.name, role: user.role || "member" };
}

export async function setSession(user: { userId: string; email: string; name: string; role?: "admin" | "member" }) {
  const sid = randomBytes(32).toString("base64url");
  const expiresAt = new Date(Date.now() + MAX_AGE_SECONDS * 1000);
  const db = await getDb();
  await verifyAuthIndexes(db);
  await db.collection("sessions").insertOne({ sid, userId: user.userId, expiresAt });
  const token = createToken({ ...user, role: user.role || "member", sid, exp: expiresAt.getTime() });
  const cookieStore = await cookies();
  cookieStore.set(COOKIE_NAME, token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "strict",
    path: "/",
    maxAge: MAX_AGE_SECONDS,
  });
}

export function isSameOriginRequest(request: Request) {
  const origin = request.headers.get("origin");
  if (!origin) return process.env.NODE_ENV !== "production";
  try {
    return new URL(origin).origin === new URL(request.url).origin;
  } catch {
    return false;
  }
}

export async function clearSession() {
  const cookieStore = await cookies();
  const existing = verifyToken(cookieStore.get(COOKIE_NAME)?.value);
  if (existing && process.env.MONGODB_URI) {
    try {
      const db = await getDb();
      await db.collection("sessions").deleteOne({ sid: existing.sid, userId: existing.userId });
    } catch {
      // Clearing the browser cookie still completes logout if the session DB
      // is temporarily unavailable; server-side expiry remains bounded.
    }
  }
  cookieStore.delete(COOKIE_NAME);
}

export async function currentSession() {
  const cookieStore = await cookies();
  const session = verifyToken(cookieStore.get(COOKIE_NAME)?.value);
  if (!session) return null;
  try {
    const db = await getDb();
    await verifyAuthIndexes(db);
    const active = await db.collection("sessions").findOne({
      sid: session.sid,
      userId: session.userId,
      expiresAt: { $gt: new Date() },
    });
    return active ? session : null;
  } catch {
    return null;
  }
}

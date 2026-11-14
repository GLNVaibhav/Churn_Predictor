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

type RegistrationOperation =
  | "mongodb_connection_authentication"
  | "index_users_email_unique"
  | "index_sessions_sid_unique"
  | "index_sessions_expires_at_ttl"
  | "existing_user_lookup"
  | "user_insertion";

let clientPromise: Promise<MongoClient> | null = null;
let indexesPromise: Promise<void> | null = null;

function authSecret() {
  return process.env.AUTH_SECRET || "";
}

function safeIdentifier(value: unknown) {
  return typeof value === "string" && /^[A-Za-z][A-Za-z0-9_.-]{0,63}$/.test(value) ? value : undefined;
}

function safeCode(value: unknown) {
  return typeof value === "number" || (typeof value === "string" && /^[A-Za-z0-9_.-]{1,64}$/.test(value)) ? value : undefined;
}

function safeMongoRejectionReason(error: unknown) {
  const message = error instanceof Error ? error.message : "";
  const denied = message.match(/not authorized to do action\s+\[([A-Za-z]+)\]\s+on\s+\[([A-Za-z0-9_.-]+)\]/i);
  if (denied) return `not_authorized:${denied[1]}:${denied[2]}`;
  if (/bad auth|authentication failed/i.test(message)) return "authentication_rejected";
  if (/indexoptionsconflict|already exists.*different options/i.test(message)) return "index_options_conflict";
  if (/duplicate key|e11000/i.test(message)) return "duplicate_key_conflict";
  if (/too many indexes|index.*limit/i.test(message)) return "index_limit";
  if (/quota|storage.*limit/i.test(message)) return "storage_or_quota_limit";
  if (/index build|createindex/i.test(message)) return "index_build_rejected";
  return "unclassified_mongo_rejection";
}

async function safeIndexAuthorizationContext(db: Db) {
  try {
    const status = await db.command({ connectionStatus: 1, showPrivileges: true });
    const authInfo = status.authInfo || {};
    const authenticationDatabases = [...new Set(
      (authInfo.authenticatedUsers || []).map((user: { db?: unknown }) => safeIdentifier(user?.db)).filter(Boolean),
    )];
    const effectiveRoles = [...new Set(
      (authInfo.authenticatedUserRoles || []).map((role: { role?: unknown; db?: unknown }) => {
        const name = safeIdentifier(role?.role);
        const database = safeIdentifier(role?.db);
        return name && database ? `${name}@${database}` : undefined;
      }).filter(Boolean),
    )];
    const hasCreateIndexPrivilege = (authInfo.authenticatedUserPrivileges || []).some((privilege: {
      resource?: { db?: unknown };
      actions?: unknown;
    }) => {
      const resourceDatabase = privilege.resource?.db;
      return (resourceDatabase === db.databaseName || resourceDatabase === "")
        && Array.isArray(privilege.actions)
        && privilege.actions.includes("createIndex");
    });
    return {
      selectedDatabase: db.databaseName,
      authenticationDatabases,
      effectiveRoles,
      hasCreateIndexPrivilege,
    };
  } catch {
    return { selectedDatabase: db.databaseName, authorizationContext: "unavailable" };
  }
}

async function safeExistingIndexes(db: Db, collection: "users" | "sessions") {
  try {
    const indexes = await db.collection(collection).listIndexes().toArray();
    return indexes.map((index) => ({
      name: safeIdentifier(index.name),
      keys: Object.fromEntries(
        Object.entries(index.key || {}).flatMap(([field, direction]) => {
          const safeField = safeIdentifier(field);
          return safeField ? [[safeField, typeof direction === "number" ? direction : safeIdentifier(direction)]] : [];
        }),
      ),
      unique: index.unique === true,
      expireAfterSeconds: typeof index.expireAfterSeconds === "number" ? index.expireAfterSeconds : undefined,
    }));
  } catch {
    return "unavailable";
  }
}

async function withRegistrationDiagnostic<T>(operation: RegistrationOperation, action: () => Promise<T>): Promise<T> {
  try {
    return await action();
  } catch (error) {
    const diagnostic = error as { name?: unknown; code?: unknown; codeName?: unknown };
    console.error("[auth/register]", {
      operation,
      errorName: safeIdentifier(diagnostic?.name) || "UnknownError",
      code: safeCode(diagnostic?.code),
      codeName: safeIdentifier(diagnostic?.codeName),
    });
    throw error;
  }
}

async function withIndexDiagnostic<T>(
  operation: RegistrationOperation,
  db: Db,
  collection: "users" | "sessions",
  action: () => Promise<T>,
): Promise<T> {
  try {
    return await action();
  } catch (error) {
    const diagnostic = error as { name?: unknown; code?: unknown; codeName?: unknown };
    console.error("[auth/register]", {
      operation,
      errorName: safeIdentifier(diagnostic?.name) || "UnknownError",
      code: safeCode(diagnostic?.code),
      codeName: safeIdentifier(diagnostic?.codeName),
      rejectionReason: safeMongoRejectionReason(error),
      ...await safeIndexAuthorizationContext(db),
      existingIndexes: await safeExistingIndexes(db, collection),
    });
    throw error;
  }
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

async function ensureAuthIndexes(db: Db) {
  if (!indexesPromise) {
    indexesPromise = Promise.all([
      withIndexDiagnostic("index_users_email_unique", db, "users", () =>
        db.collection<UserDoc>("users").createIndex({ email: 1 }, { unique: true }),
      ),
      withIndexDiagnostic("index_sessions_sid_unique", db, "sessions", () =>
        db.collection("sessions").createIndex({ sid: 1 }, { unique: true }),
      ),
      withIndexDiagnostic("index_sessions_expires_at_ttl", db, "sessions", () =>
        db.collection("sessions").createIndex({ expiresAt: 1 }, { expireAfterSeconds: 0 }),
      ),
    ]).then(() => undefined).catch((error) => {
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
  const db = await withRegistrationDiagnostic("mongodb_connection_authentication", getDb);
  await ensureAuthIndexes(db);
  const normalizedEmail = email.trim().toLowerCase();
  const existing = await withRegistrationDiagnostic("existing_user_lookup", () =>
    db.collection<UserDoc>("users").findOne({ email: normalizedEmail }),
  );
  if (existing) throw new Error("Account already exists");
  const hashed = hashPassword(password);
  const now = new Date();
  const result = await withRegistrationDiagnostic("user_insertion", () =>
    db.collection<UserDoc>("users").insertOne({
      _id: new ObjectId(),
      email: normalizedEmail,
      name: name.trim() || normalizedEmail.split("@")[0],
      role,
      ...hashed,
      createdAt: now,
      updatedAt: now,
    }),
  );
  return { userId: result.insertedId.toString(), email: normalizedEmail, name: name.trim() || normalizedEmail.split("@")[0], role };
}

export async function authenticateUser(email: string, password: string) {
  const db = await getDb();
  const user = await db.collection<UserDoc>("users").findOne({ email: email.trim().toLowerCase() });
  if (!user || !verifyPassword(password, user)) throw new Error("Invalid email or password");
  return { userId: user._id.toString(), email: user.email, name: user.name, role: user.role || "member" };
}

export async function setSession(user: { userId: string; email: string; name: string; role?: "admin" | "member" }) {
  const sid = randomBytes(32).toString("base64url");
  const expiresAt = new Date(Date.now() + MAX_AGE_SECONDS * 1000);
  const db = await getDb();
  await ensureAuthIndexes(db);
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

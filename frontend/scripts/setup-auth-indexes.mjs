import { MongoClient } from "mongodb";

const DEVELOPMENT_DATABASE = "ucif_development";
const REQUIRED_INDEXES = [
  { collection: "users", key: { email: 1 }, name: "email_1", unique: true },
  { collection: "sessions", key: { sid: 1 }, name: "sid_1", unique: true },
  { collection: "sessions", key: { expiresAt: 1 }, name: "expiresAt_1", expireAfterSeconds: 0 },
];

class SetupFailure extends Error {
  constructor(reason) {
    super(reason);
    this.reason = reason;
  }
}

function sameKey(actual, expected) {
  const actualEntries = Object.entries(actual ?? {});
  const expectedEntries = Object.entries(expected);
  return actualEntries.length === expectedEntries.length
    && expectedEntries.every(([field, direction], index) =>
      actualEntries[index]?.[0] === field && actualEntries[index]?.[1] === direction);
}

function indexMatches(index, required) {
  return sameKey(index.key, required.key)
    && (required.unique === true ? index.unique === true : index.unique !== true)
    && index.expireAfterSeconds === required.expireAfterSeconds
    && !index.sparse
    && !index.partialFilterExpression
    && !index.collation;
}

function safeMongoFields(error) {
  const value = error && typeof error === "object" ? error : {};
  return {
    reason: typeof value.reason === "string" && /^[a-z0-9_]{1,64}$/.test(value.reason) ? value.reason : undefined,
    errorName: typeof value.name === "string" && /^[A-Za-z][A-Za-z0-9_.-]{0,63}$/.test(value.name) ? value.name : "UnknownError",
    mongoCode: typeof value.code === "number" || (typeof value.code === "string" && /^[A-Za-z0-9_.-]{1,64}$/.test(value.code))
      ? value.code
      : undefined,
    mongoCodeName: typeof value.codeName === "string" && /^[A-Za-z][A-Za-z0-9_.-]{0,63}$/.test(value.codeName)
      ? value.codeName
      : undefined,
  };
}

async function verifyDevelopmentIdentity(db) {
  const status = await db.command({ connectionStatus: 1, showPrivileges: true });
  const authInfo = status.authInfo ?? {};
  const expectedUser = (authInfo.authenticatedUsers ?? []).some((user) =>
    user.user === "ucif_dev_app" && user.db === "admin");
  const expectedRole = (authInfo.authenticatedUserRoles ?? []).some((role) =>
    role.role === "readWrite" && role.db === DEVELOPMENT_DATABASE);
  const canCreateIndexes = (authInfo.authenticatedUserPrivileges ?? []).some((privilege) =>
    (privilege.resource?.db === DEVELOPMENT_DATABASE || privilege.resource?.db === "")
      && Array.isArray(privilege.actions)
      && privilege.actions.includes("createIndex"));

  if (!expectedUser || !expectedRole || !canCreateIndexes) {
    throw new Error("Configured MongoDB identity is not the expected scoped development user.");
  }
}

async function ensureCollection(db, name) {
  const exists = await db.listCollections({ name }, { nameOnly: true }).hasNext();
  if (!exists) await db.createCollection(name);
}

async function hasDuplicateValues(collection, field) {
  return collection.aggregate([
    { $group: { _id: `$${field}`, count: { $sum: 1 } } },
    { $match: { count: { $gt: 1 } } },
    { $limit: 1 },
  ], { maxTimeMS: 15_000 }).hasNext();
}

async function initializeIndexes(db, setOperation) {
  for (const required of REQUIRED_INDEXES) {
    setOperation(`inspect_collection_${required.collection}`);
    await ensureCollection(db, required.collection);
    const collection = db.collection(required.collection);
    setOperation(`inspect_indexes_${required.collection}`);
    const indexes = await collection.listIndexes().toArray();
    const sameKeyIndex = indexes.find((index) => sameKey(index.key, required.key));

    if (sameKeyIndex) {
      if (!indexMatches(sameKeyIndex, required)) {
        throw new SetupFailure("existing_index_incompatible");
      }
      console.log(`verified ${required.name}`);
      continue;
    }

    if (required.unique) {
      setOperation(`check_duplicates_${required.collection}_${Object.keys(required.key)[0]}`);
      if (await hasDuplicateValues(collection, Object.keys(required.key)[0])) {
        throw new SetupFailure("duplicate_values_for_unique_index");
      }
    }

    const options = {
      name: required.name,
      ...(required.unique ? { unique: true } : {}),
      ...(required.expireAfterSeconds !== undefined ? { expireAfterSeconds: required.expireAfterSeconds } : {}),
    };
    setOperation(`create_index_${required.collection}_${Object.keys(required.key)[0]}`);
    await collection.createIndex(required.key, options);

    setOperation(`verify_index_${required.collection}_${Object.keys(required.key)[0]}`);
    const created = (await collection.listIndexes().toArray()).find((index) => sameKey(index.key, required.key));
    if (!created || !indexMatches(created, required)) {
      throw new SetupFailure("required_index_verification_failed");
    }
    console.log(`created and verified ${required.name}`);
  }
}

async function main() {
  let client;
  let operation = "validate_configuration";
  try {
    const uri = process.env.MONGODB_URI;
    const databaseName = process.env.MONGODB_DB;
    const confirmation = process.env.UCIF_AUTH_INDEX_SETUP_CONFIRM;
    if (!uri) throw new SetupFailure("missing_mongodb_uri");
    if (databaseName !== DEVELOPMENT_DATABASE || confirmation !== DEVELOPMENT_DATABASE) {
      throw new SetupFailure("development_database_confirmation_required");
    }

    client = new MongoClient(uri, { serverSelectionTimeoutMS: 10_000 });
    operation = "connect";
    await client.connect();
    const db = client.db(DEVELOPMENT_DATABASE);
    operation = "verify_development_identity";
    await verifyDevelopmentIdentity(db);
    await initializeIndexes(db, (nextOperation) => { operation = nextOperation; });
    console.log("development authentication indexes are ready");
  } catch (error) {
    console.error(JSON.stringify({ operation, ...safeMongoFields(error) }));
    process.exitCode = 1;
  } finally {
    await client?.close().catch(() => undefined);
  }
}

await main();

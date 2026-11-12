# UCIF Production Readiness and Deployment

## Current architecture

The Next.js application is a same-origin backend-for-frontend (BFF). In production it requires a valid `ucif_session` cookie, validates its signature, expiry and active MongoDB session, then sends the verified user ID and role to FastAPI with a server-only shared secret. FastAPI rejects protected requests without that secret and scopes dataset profiles and executions to the verified owner. Uploads and executions are linked by IDs; the context document is stored in the execution record. Reports and exports are derived from that execution record.

For local development, explicitly set `UCIF_AUTH_MODE=development` on the API. Production is the default when this variable is absent. Development mode deliberately bypasses authentication and is only safe on a developer-controlled machine bound to loopback. Never use it on an internet-accessible service.

## Production topology

Deploy Next.js and FastAPI as separate services. Vercel is suitable for the Next.js frontend. Run FastAPI on a persistent container or application service with background-task capacity; do not run the analysis service as an ephemeral serverless function. PostgreSQL stores upload profiles and execution JSON records. A private S3-compatible bucket stores source CSVs. The application currently persists generated report text and report metadata in PostgreSQL JSONB; downloadable JSON/CSV/TXT representations are generated from the persisted execution response.

The FastAPI service must be reachable from the Next.js server but should not be directly exposed to browsers. If it must have a public network address, keep the shared secret in the service secret manager and enforce TLS and network-level ingress restrictions as well. Do not put `UCIF_PROXY_SECRET` in a `NEXT_PUBLIC_*` variable.

## Environment variables

### Next.js

| Variable | Requirement | Purpose |
|---|---|---|
| `BACKEND_URL` | Required in deployment | Private HTTPS origin of FastAPI, e.g. `https://api.example.com`; server-side only. |
| `UCIF_PROXY_SECRET` | Required | Random secret of at least 32 characters, identical to the FastAPI setting. |
| `MONGODB_URI` | Required for sign-in | MongoDB connection string from the secret manager. |
| `MONGODB_DB` | Optional | Auth database name; defaults to `ucif`. |
| `AUTH_SECRET` | Required | Random signing secret of at least 32 characters for the HttpOnly session cookie. |
| `ADMIN_SETUP_TOKEN` | Optional, temporary setup only | High-entropy token for the one-time bootstrap endpoint; remove after initial admin provisioning. |

### FastAPI

| Variable | Requirement | Purpose |
|---|---|---|
| `UCIF_AUTH_MODE` | Set to `production` | Enables fail-closed auth and production storage checks. |
| `UCIF_PROXY_SECRET` | Required | Same random BFF secret as Next.js. |
| `DATABASE_URL` | Required | PostgreSQL DSN; use TLS/`sslmode=require` and secret-managed credentials. |
| `OBJECT_STORAGE_BACKEND` | Set to `s3` | Enables durable upload storage. |
| `S3_BUCKET` | Required | Private bucket name. |
| `AWS_REGION` | Required by AWS deployments | Region; use the workload's IAM role where available rather than static access keys. |
| `S3_ENDPOINT_URL` | Optional | Endpoint for a compatible object store. |
| `CORS_ORIGINS` | Optional | Comma-separated browser origins. Same-origin BFF use normally needs no direct browser CORS origin. |

No credential values belong in `.env.example`, source control, browser code, or logs. The checked-in examples are templates only; the application does not automatically load `.env` files for FastAPI.

## Storage initialization and retention

The API creates `ucif_records` and its owner index on PostgreSQL startup. The initial schema is:

```sql
CREATE TABLE ucif_records (
  record_id TEXT PRIMARY KEY,
  owner_id TEXT,
  data JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ucif_records_owner_idx ON ucif_records (owner_id);
```

For managed deployments, provision the same schema using a migration job before rollout; the runtime `CREATE TABLE IF NOT EXISTS` is a bootstrap convenience, not a versioned migration system. Use PostgreSQL backups/PITR and private bucket encryption/versioning. The API includes owner-checked deletion for upload records and completed executions. Define the retention period with the data controller and schedule `python scripts/purge_expired_records.py --older-than-days <approved-days>` as a daily host job. It removes aged, non-running records and corresponding source CSVs from S3. Configure private-bucket lifecycle/version retention separately through the storage provider; automatic scheduling is not enabled by this repository.

Local development continues to use atomic JSON records and filesystem uploads. PostgreSQL and S3 adapters are configurable and covered by local adapter tests, but no cloud database or object store was available for live verification in this work session.

## Build and run

### Backend service

```powershell
python -m pip install -r requirements.txt
$env:UCIF_AUTH_MODE = "production"
# Set DATABASE_URL, UCIF_PROXY_SECRET, OBJECT_STORAGE_BACKEND=s3,
# S3_BUCKET, AWS_REGION, and credentials/role through the host secret manager.
python -m uvicorn backend.api.app:app --host 0.0.0.0 --port 8000
```

Run the backend behind TLS at the configured private origin. `GET /api/v1/health` is an unauthenticated liveness check; it does not prove database or S3 readiness. Verify authenticated upload, profile, execution, status, prediction, decision and report paths after provisioning.

### Frontend on Vercel

The repository layout places the Next.js application under `frontend/`. The candidate files suggest a Vercel Root Directory of `frontend`, build command `npm run build`, and install command `npm ci`. The actual Vercel project settings could not be read during this audit, so do not treat those repository values as verified project configuration. Confirm Root Directory, framework preset, build/install commands, Node version, and production environment variables in the Vercel project before deployment.

Run `npm ci`, `npm run lint`, `npx tsc --noEmit`, and `npm run build` from `frontend/` in CI. Configure production variables only in Vercel's environment-variable store. The API proxy must target the FastAPI HTTPS origin and share the proxy secret.

## Health checks and rollback

1. Check `/api/v1/health` for process liveness.
2. From the frontend deployment, verify the proxy returns 401 without a session and only returns data after sign-in.
3. Using a non-sensitive test CSV, verify upload, owner-scoped history, analysis, predictions, context recommendations, and report exports.
4. Verify a second test account receives 404 for the first account's upload and execution IDs.
5. Restart FastAPI and verify PostgreSQL records and S3 objects remain accessible.
6. For rollback, route frontend traffic to the prior Vercel deployment and backend traffic to the prior compatible image. Do not roll back schema changes without a tested database migration rollback. Preserve object data and database backups.

## Release blockers and limits

- Vercel project settings and Root Directory have not been verified; the authenticated project lookup was denied by Vercel scope authorization.
- Production authentication requires MongoDB, `AUTH_SECRET`, `UCIF_PROXY_SECRET`, and first-admin provisioning. Authenticated browser login was not live-tested because no MongoDB credentials were configured.
- PostgreSQL and S3 adapters have not been tested against actual cloud services.
- Automatic retention scheduling and durable background-job recovery are not implemented. Schedule the purge command after the data-retention period is approved. FastAPI's current in-process task manager does not survive a process restart; production needs a durable worker/queue before relying on long-running jobs.
- Rate limiting and abuse monitoring require an edge/API gateway policy; the current in-process service has no distributed rate limiter.
- The release does not pass all existing backend tests until the regenerated coverage baseline test is verified.

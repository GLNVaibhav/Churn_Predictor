import os
from pathlib import Path
from urllib.parse import urlsplit

# Base directory of the repository
BASE_DIR = Path(__file__).resolve().parents[2]

# Directory where uploaded CSVs and metadata are stored
UPLOAD_ROOT = BASE_DIR / "data" / "uploads"

# Ensure the upload directory exists
os.makedirs(UPLOAD_ROOT, exist_ok=True)

# Directory for execution run data (e.g., intermediate results)
RUN_ROOT = BASE_DIR / "data" / "runs"
os.makedirs(RUN_ROOT, exist_ok=True)

# Version information (keep in sync with package versions)
FRAMEWORK_VERSION = "1.0.0"
RUNTIME_VERSION = "1.0.0"
API_VERSION = "v1"

# Production browser traffic should use the same-origin Next.js BFF. Direct
# CORS origins are explicit and configurable for local development only.
_default_auth_mode = "production"
AUTH_MODE = os.getenv("UCIF_AUTH_MODE", _default_auth_mode).lower()
_default_cors_origins = [] if AUTH_MODE == "production" else [
    "http://localhost:3000", "http://127.0.0.1:3000",
    "http://localhost:5000", "http://127.0.0.1:5000",
]
CORS_ORIGINS = [
    origin.strip().rstrip("/")
    for origin in os.getenv("CORS_ORIGINS", ",".join(_default_cors_origins)).split(",")
    if origin.strip()
]

UCIF_PROXY_SECRET = os.getenv("UCIF_PROXY_SECRET", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")
OBJECT_STORAGE_BACKEND = os.getenv("OBJECT_STORAGE_BACKEND", "filesystem").lower()
S3_BUCKET = os.getenv("S3_BUCKET", "")

# Limits
MAX_UPLOAD_SIZE = int(os.getenv("MAX_UPLOAD_SIZE", str(10 * 1024 * 1024)))

import os
from pathlib import Path

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

# CORS allowed origins for development
CORS_ORIGINS = [
    "http://localhost:5000",
    "http://127.0.0.1:5000",
]

# Limits
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB

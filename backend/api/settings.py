from pathlib import Path

# Base directory of the project (two levels up from this file)
BASE_DIR = Path(__file__).resolve().parents[2]

# Directory where uploaded CSV files are stored
UPLOAD_ROOT = BASE_DIR / "data" / "uploads"

# Directory for runtime execution outputs (used by ExecutionRepository)
RUN_ROOT = BASE_DIR / "outputs" / "runs"

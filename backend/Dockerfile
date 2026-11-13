FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

WORKDIR /app

# XGBoost's Linux runtime requires OpenMP. psycopg uses its bundled binary wheel.
RUN apt-get update \
    && apt-get install --no-install-recommends -y libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./requirements.txt
RUN python -m pip install -r requirements.txt

# Include only the live API/framework sources, semantic knowledge, and the
# saved inference bundle. Dataset inputs and notebook/training outputs are
# excluded by the root .dockerignore.
COPY backend ./backend
COPY universal_churn ./universal_churn
COPY knowledge ./knowledge
COPY outputs/universal ./outputs/universal

RUN groupadd --system ucif \
    && useradd --system --gid ucif --home-dir /app --no-create-home ucif \
    && install -d --owner=ucif --group=ucif /app/data/uploads /app/data/runs \
    && chown -R ucif:ucif /app

USER ucif

EXPOSE 8000

# One worker is intentional: execution tasks are currently managed in-process.
# Staging still requires a durable task-recovery design before production use.
CMD ["sh", "-c", "exec python -m uvicorn backend.api.app:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]

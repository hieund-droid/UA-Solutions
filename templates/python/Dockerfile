# syntax=docker/dockerfile:1.7

FROM python:3.12-slim-bookworm AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# --- Install deps ---
FROM base AS deps
WORKDIR /app
COPY requirements.txt pip.conf ./
RUN python -m pip install --upgrade pip && python -m pip install -r requirements.txt

# --- Runtime (non-root) ---
FROM base AS runtime
RUN groupadd --system app && useradd --system --gid app --home /app app
WORKDIR /app
COPY --from=deps /usr/local/lib/python3.12 /usr/local/lib/python3.12
COPY --from=deps /usr/local/bin /usr/local/bin
COPY --chown=app:app src ./src
USER app

# HTTP-service shape adds `EXPOSE 8000` above this line — see
# shapes/http-service/Dockerfile-additions.txt.
CMD ["python", "-m", "src.main"]

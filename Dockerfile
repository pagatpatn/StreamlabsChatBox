# ----------------------------
# Stage 1: Builder
# ----------------------------
FROM python:3.12-slim-bullseye AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install only what's needed to build wheels + Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl ca-certificates wget unzip git build-essential \
      libasound2 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
      libxcomposite1 libxdamage1 libxrandr2 libgbm1 \
      libpango-1.0-0 libpangocairo-1.0-0 libnss3 \
      libxfixes3 libxkbcommon0 fonts-liberation xdg-utils \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel \
    && pip install -r requirements.txt \
    && pip install playwright

# Install Chromium only (no Firefox/WebKit bloat)
RUN playwright install --with-deps chromium

# ----------------------------
# Stage 2: Runtime
# ----------------------------
FROM python:3.12-slim-bullseye

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Only minimal runtime libs for Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
      libasound2 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
      libxcomposite1 libxdamage1 libxrandr2 libgbm1 \
      libpango-1.0-0 libpangocairo-1.0-0 libnss3 \
      libxfixes3 libxkbcommon0 fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages + Chromium from builder
COPY --from=builder /usr/local /usr/local
COPY --from=builder /root/.cache/ms-playwright /root/.cache/ms-playwright

# Copy only your app (no .dockerignore → still clean)
COPY . .

CMD ["python", "str.py"]

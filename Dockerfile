# ----------------------------
# Stage 1: Builder
# ----------------------------
FROM python:3.12-slim-bullseye AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install Chromium build dependencies + basic tools
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl ca-certificates fonts-liberation \
      libasound2 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
      libxcomposite1 libxdamage1 libxrandr2 libgbm1 \
      libpango-1.0-0 libpangocairo-1.0-0 libnss3 \
      xdg-utils wget unzip git \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install playwright

# Install ONLY Chromium (not all browsers)
RUN playwright install chromium

# ----------------------------
# Stage 2: Runtime
# ----------------------------
FROM python:3.12-slim-bullseye

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Minimal Chromium runtime deps
RUN apt-get update && apt-get install -y --no-install-recommends \
      libasound2 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
      libxcomposite1 libxdamage1 libxrandr2 libgbm1 \
      libpango-1.0-0 libpangocairo-1.0-0 libnss3 \
      libxfixes3 libxkbcommon0 \
      fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Copy Python deps + Chromium
COPY --from=builder /usr/local /usr/local
COPY --from=builder /root/.cache/ms-playwright /root/.cache/ms-playwright

# Copy app
COPY . .

CMD ["python", "str.py"]

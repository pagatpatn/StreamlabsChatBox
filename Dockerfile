# ----------------------------
# Stage 1: Builder (installs Python deps + Playwright Chromium)
# ----------------------------
FROM python:3.12-slim-bullseye AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps needed just to install & run Chromium once
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl ca-certificates fonts-liberation \
      libasound2 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
      libxcomposite1 libxdamage1 libxrandr2 libgbm1 \
      libpango-1.0-0 libpangocairo-1.0-0 libnss3 \
      xdg-utils wget unzip git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements & install
COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install playwright

# Install ONLY Chromium (not all browsers)
RUN playwright install --with-deps chromium

# ----------------------------
# Stage 2: Runtime (slimmed down)
# ----------------------------
FROM python:3.12-slim-bullseye

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Minimal runtime libraries Chromium needs
RUN apt-get update && apt-get install -y --no-install-recommends \
      libasound2 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
      libxcomposite1 libxdamage1 libxrandr2 libgbm1 \
      libpango-1.0-0 libpangocairo-1.0-0 libnss3 \
      fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Copy Python deps & Playwright Chromium from builder
COPY --from=builder /usr/local /usr/local

# Copy app files
COPY . .

# Run script
CMD ["python", "str.py"]

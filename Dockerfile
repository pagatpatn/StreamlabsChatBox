# ----------------------------
# Stage 1: Builder
# ----------------------------
FROM python:3.12-slim-bullseye

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install only essential system dependencies for Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
        libnss3 \
        libatk1.0-0 \
        libatk-bridge2.0-0 \
        libcups2 \
        libxcomposite1 \
        libxdamage1 \
        libxrandr2 \
        libgbm1 \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libasound2 \
        fonts-liberation \
        libappindicator3-1 \
        xdg-utils \
        wget \
        unzip \
    && rm -rf /var/lib/apt/lists/*

# Set workdir
WORKDIR /app

# Install Python deps
COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt

# Install Playwright + Chromium only
RUN pip install playwright && playwright install chromium


# ----------------------------
# Stage 2: Final runtime image
# ----------------------------
FROM python:3.12-bookworm-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Copy Chromium runtime deps from builder
COPY --from=builder /usr/lib /usr/lib
COPY --from=builder /usr/bin /usr/bin
COPY --from=builder /usr/share /usr/share

# Copy installed Python packages from builder
COPY --from=builder /usr/local /usr/local

# Set workdir
WORKDIR /app

# Copy app source
COPY . .

# Default command
CMD ["python", "str.py"]

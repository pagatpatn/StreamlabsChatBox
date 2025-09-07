# ----------------------------
# Base image
# ----------------------------
FROM python:3.12-slim

# ----------------------------
# Environment
# ----------------------------
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# ----------------------------
# System dependencies for Playwright
# ----------------------------
RUN apt-get update && apt-get install -y \
        curl \
        gnupg \
        ca-certificates \
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
        git \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

# ----------------------------
# Set workdir
# ----------------------------
WORKDIR /app

# ----------------------------
# Copy requirements
# ----------------------------
COPY requirements.txt .

# Upgrade pip & install dependencies
RUN pip install --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt

# ----------------------------
# Install Playwright Chromium
# ----------------------------
RUN playwright install chromium

# ----------------------------
# Copy your script
# ----------------------------
COPY . .

# ----------------------------
# Run your script
# ----------------------------
CMD ["python", "str.py"]

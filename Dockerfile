# --------------------------
# Base image
# --------------------------
FROM python:3.13-slim

# --------------------------
# Environment variables
# --------------------------
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# --------------------------
# Install system dependencies for Chromium/Playwright + build tools
# --------------------------
RUN apt-get update && apt-get install -y \
    wget curl gnupg \
    build-essential python3-dev \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libx11-xcb1 libxcb1 libxcomposite1 \
    libxdamage1 libxrandr2 libgbm1 libasound2 libpango-1.0-0 libgtk-3-0 \
    fonts-liberation libappindicator3-1 libxss1 xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# --------------------------
# Set working directory
# --------------------------
WORKDIR /app

# --------------------------
# Copy requirements and install Python deps
# --------------------------
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --------------------------
# Install Playwright browsers
# --------------------------
RUN playwright install --with-deps

# --------------------------
# Copy the app code
# --------------------------
COPY . .

# --------------------------
# Entrypoint
# --------------------------
CMD ["python", "main.py"]

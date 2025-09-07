# Base image
FROM python:3.13-slim

# Install minimal dependencies for Chromium + Playwright
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    ca-certificates \
    fonts-liberation \
    libnss3 \
    libx11-xcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxrandr2 \
    libasound2 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    libxss1 \
    libdbus-glib-1-2 \
    libgbm1 \
    wget \
    unzip \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Chromium + dependencies for Playwright
RUN playwright install --with-deps chromium

# Copy the chat capture script
COPY str.py .

# Default command
CMD ["python", "str.py"]

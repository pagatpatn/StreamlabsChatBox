# --------------------------
# Base image
# --------------------------
FROM python:3.12-slim

# --------------------------
# Install system dependencies for Playwright
# --------------------------
RUN apt-get update && \
    apt-get install -y \
        curl \
        wget \
        unzip \
        gnupg \
        libnss3 \
        libatk1.0-0 \
        libatk-bridge2.0-0 \
        libcups2 \
        libdrm2 \
        libxkbcommon0 \
        libxcomposite1 \
        libxdamage1 \
        libxrandr2 \
        libgbm1 \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libgtk-3-0 \
        libasound2 \
        libxcb1 \
        libx11-xcb1 \
        libxss1 \
        libxtst6 \
        libxext6 \
        libxrender1 \
        libxfixes3 \
        libxcursor1 \
        libxi6 \
        libc6 \
        gcc \
        g++ \
        && rm -rf /var/lib/apt/lists/*

# --------------------------
# Set working directory
# --------------------------
WORKDIR /app

# --------------------------
# Copy requirements and install Python packages
# --------------------------
COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# --------------------------
# Install Playwright browsers and dependencies
# --------------------------
RUN playwright install --with-deps

# --------------------------
# Copy your application code
# --------------------------
COPY . .

# --------------------------
# Set entrypoint
# --------------------------
CMD ["python", "str.py"]

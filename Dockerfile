# --------------------------
# Base image
# --------------------------
FROM python:3.12-slim

# --------------------------
# Install system dependencies
# --------------------------
RUN apt-get update && \
    apt-get install -y \
        gcc \
        g++ \
        curl \
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
        wget \
        unzip \
        && rm -rf /var/lib/apt/lists/*

# --------------------------
# Set working directory
# --------------------------
WORKDIR /app

# --------------------------
# Copy requirements and install Python packages
# --------------------------
COPY requirements.txt .
# Force greenlet to 3.0.3 (compatible with Python 3.12)
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# --------------------------
# Install Playwright browsers
# --------------------------
RUN playwright install

# --------------------------
# Copy your application code
# --------------------------
COPY . .

# --------------------------
# Set entrypoint
# --------------------------
CMD ["python", "main.py"]

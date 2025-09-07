# Use Python base
FROM python:3.13-slim

# Install system dependencies for Playwright + Chromium
RUN apt-get update && apt-get install -y \
    wget \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpangocairo-1.0-0 \
    libpango-1.0-0 \
    libcairo2 \
    && rm -rf /var/lib/apt/lists/*

# Install python deps
COPY requirements.txt .
RUN pip install -r requirements.txt

# Install Playwright browsers (Chromium only to save space)
RUN playwright install --with-deps chromium

# Copy app
COPY . /app
WORKDIR /app

CMD ["python", "str.py"]

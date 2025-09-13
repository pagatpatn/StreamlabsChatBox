# ----------------------------
# Base image
# ----------------------------
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# ----------------------------
# Install ONLY Chromium deps
# ----------------------------
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
    ca-certificates \
    wget \
 && rm -rf /var/lib/apt/lists/*

# ----------------------------
# Install Python deps
# ----------------------------
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
 && pip install --no-cache-dir -r requirements.txt \
 && pip install --no-cache-dir playwright

# ----------------------------
# Install minimal Chromium
# ----------------------------
RUN playwright install --with-deps chromium

# ----------------------------
# Copy app source
# ----------------------------
COPY . .

# ----------------------------
# Run script
# ----------------------------
CMD ["python", "str.py"]

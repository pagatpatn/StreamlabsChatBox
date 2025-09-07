# Base image
FROM python:3.13-slim

# Install system dependencies for Chromium/Playwright
RUN apt-get update && apt-get install -y \
    wget curl gnupg \
    libnss3 libatk-1.0-0 libatk-bridge2.0-0 libx11-xcb1 libxcb1 libxcomposite1 \
    libxdamage1 libxrandr2 libgbm1 libasound2 libpangocairo-1.0-0 libgtk-3-0 \
    fonts-liberation libappindicator3-1 libxss1 xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# Copy Python dependencies and install
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install chromium

# Copy app
COPY . /app
WORKDIR /app

# Command to run
CMD ["python", "main.py"]

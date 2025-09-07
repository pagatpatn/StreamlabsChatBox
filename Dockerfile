# --------------------------
# Base image
# --------------------------
FROM python:3.13-slim

# --------------------------
# Set working directory
# --------------------------
WORKDIR /app

# --------------------------
# Install system dependencies for Chromium/Playwright
# --------------------------
RUN apt-get update && apt-get install -y \
    wget curl gnupg \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libx11-xcb1 libxcb1 libxcomposite1 \
    libxdamage1 libxrandr2 libgbm1 libasound2 libpango-1.0-0 libgtk-3-0 \
    fonts-liberation libappindicator3-1 libxss1 xdg-utils \
    && rm -rf /var/lib/apt/lists/*

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
# Copy app code
# --------------------------
COPY . .

# --------------------------
# Expose port if needed
# --------------------------
# EXPOSE 8000

# --------------------------
# Run the app
# --------------------------
CMD ["python", "main.py"]

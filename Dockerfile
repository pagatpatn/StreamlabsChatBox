# Use official Python slim image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies for Playwright
RUN apt-get update && apt-get install -y \
    wget curl gnupg ca-certificates fonts-liberation libnss3 \
    libx11-xcb1 libxcomposite1 libxdamage1 libxrandr2 libatk1.0-0 \
    libcups2 libdrm2 libgbm1 libasound2 libpangocairo-1.0-0 \
    libxshmfence1 libglib2.0-0 libxrender1 libjpeg62-turbo \
    libpng16-16 libwebp6 libvpx6 libfreetype6 libharfbuzz0b \
    libfribidi0 libicu70 libssl1.1 ttf-ubuntu-font-family ttf-unifont \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python deps
COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN python -m playwright install

# Copy your script
COPY . .

# Run the script
CMD ["python", "str.py"]

# -----------------------------
# Base image with Python 3.12
# -----------------------------
FROM python:3.12-slim

# -----------------------------
# Set working directory
# -----------------------------
WORKDIR /app

# -----------------------------
# Copy local files
# -----------------------------
COPY . /app

# -----------------------------
# Upgrade pip + install dependencies
# -----------------------------
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# -----------------------------
# Install Playwright browsers
# -----------------------------
RUN playwright install chromium

# -----------------------------
# Expose optional port (not needed for ntfy)
# -----------------------------
# EXPOSE 8000

# -----------------------------
# Set environment variable to avoid sandbox issues
# -----------------------------
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# -----------------------------
# Run the script
# -----------------------------
CMD ["python", "str.py"]

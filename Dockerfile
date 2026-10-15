# Dockerfile for Render Web Service Deployment
FROM python:3.11-slim

# Install system dependencies including Tesseract OCR for document image parsing
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Render dynamically sets PORT environment variable (defaulting to 10000)
ENV PORT=10000
EXPOSE 10000

# Start FastAPI uvicorn server
CMD ["sh", "-c", "uvicorn backend.app:app --host 0.0.0.0 --port ${PORT:-10000}"]

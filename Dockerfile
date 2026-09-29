# ==============================================================================
# Multi-Stage Distroless Container for Nexora
# ==============================================================================
# Stage 1: Build & install dependencies in Debian Bookworm (Python 3.11)
FROM python:3.11-slim-bookworm AS builder

WORKDIR /build

COPY requirements.txt .

# Install dependencies into dedicated site-packages directory
RUN pip install --no-cache-dir --target=/build/site-packages -r requirements.txt

# ==============================================================================
# Stage 2: Distroless Runtime (Python 3.11 Debian 12)
FROM gcr.io/distroless/python3-debian12:latest

WORKDIR /app

# Copy compiled dependencies from builder stage
COPY --from=builder /build/site-packages /app/site-packages

# Copy application source code, persistent data template, and React SPA dist
COPY src/ /app/src/
COPY data/ /app/data/
COPY ui/dist/ /app/ui/dist/
COPY main.py /app/main.py

# Configure Python path and output buffering
ENV PYTHONPATH="/app/site-packages:/app/src"
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# Start async FastAPI application via uvicorn
CMD ["-m", "uvicorn", "nexora.api.server:app", "--host", "0.0.0.0", "--port", "8000"]

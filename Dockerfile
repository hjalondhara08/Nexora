FROM python:3.11-slim

WORKDIR /app

# Install curl for health checks
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies (all pre-compiled binary wheels)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code, default data, and pre-built React UI SPA
COPY src/ ./src/
COPY data/ ./data/
COPY ui/dist/ ./ui/dist/
COPY main.py .

ENV PYTHONPATH="/app/src:${PYTHONPATH}"
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "nexora.api.server:app", "--host", "0.0.0.0", "--port", "8000"]

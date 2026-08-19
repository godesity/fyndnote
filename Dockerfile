# Stage 1: Build frontend
FROM node:20-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Backend + static frontend
FROM python:3.11-slim
WORKDIR /app/backend

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies
RUN pip install --no-cache-dir \
    fastapi>=0.141.1 \
    "pydantic>=2.13.4" \
    "uvicorn>=0.52.3" \
    "datasets>=3.5.0" \
    "pyarrow>=15.0.0" \
    "Pillow>=10.0.0" \
    "requests>=2.31.0" \
    "python-multipart>=0.0.32" \
    "boto3>=1.34.0"

# Copy backend source
COPY backend/ ./

# Seed data (users.json only — rest lives on the volume)
COPY data/users.json /app/data/users.json

# Copy built frontend
COPY --from=frontend /app/frontend/dist /app/frontend/dist

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

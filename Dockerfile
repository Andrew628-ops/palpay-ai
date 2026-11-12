
# Build the React frontend
FROM node:22-bookworm-slim AS frontend-build

WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm install --no-audit --no-fund

COPY frontend/ ./
RUN npm run build

# Run FastAPI
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY --from=frontend-build /frontend/dist ./frontend/dist

ENV PYTHONUNBUFFERED=1

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000}"]

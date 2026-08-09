FROM node:20-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS runtime
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
COPY deploy/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./backend/
COPY --from=frontend /app/frontend/dist ./frontend/dist
COPY deploy/entrypoint.sh ./entrypoint.sh
RUN chmod +x ./entrypoint.sh
ENV PYTHONPATH=/app/backend
WORKDIR /app/backend
CMD ["/app/entrypoint.sh"]

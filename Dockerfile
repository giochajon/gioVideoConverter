# --- Stage 1: build the React frontend ---
FROM node:20-slim AS frontend-build
WORKDIR /frontend
COPY frontend/package.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# --- Stage 2: runtime image with HandBrakeCLI + FastAPI backend ---
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1

RUN apt-get update && \
    apt-get install -y --no-install-recommends software-properties-common && \
    add-apt-repository -y universe && \
    apt-get update && \
    apt-get install -y --no-install-recommends handbrake-cli python3 python3-pip && \
    apt-get purge -y software-properties-common && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt ./requirements.txt
RUN pip3 install --no-cache-dir -r requirements.txt

COPY backend/app ./app
# vite.config.ts sets outDir to ../backend/app/static (relative to /frontend),
# which resolves to /backend/app/static in the build stage.
COPY --from=frontend-build /backend/app/static ./app/static

# Run as a non-root user matching the default host UID/GID (1000) used by the
# bind-mounted media/log volumes in docker-compose.yml, so file ownership lines
# up without extra chown steps on the host.
RUN groupadd -g 1000 appuser && \
    useradd -u 1000 -g appuser -M -s /usr/sbin/nologin appuser && \
    chown -R appuser:appuser /app
USER appuser

EXPOSE 9095

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:9095/', timeout=3)" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9095"]

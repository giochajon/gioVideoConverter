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

EXPOSE 9095

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9095"]

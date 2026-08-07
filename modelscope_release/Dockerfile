FROM node:20-alpine AS frontend-build
WORKDIR /src
COPY frontend/package*.json ./frontend/
WORKDIR /src/frontend
RUN npm ci
COPY frontend/ /src/frontend/
RUN npm run build

FROM python:3.13-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY app/ /app/app/
COPY scripts/ /app/scripts/
COPY modelscope_release/ /app/modelscope_release/
COPY --from=frontend-build /src/frontend/dist /app/frontend_dist

RUN chmod +x /app/modelscope_release/start.sh && mkdir -p /app/data/uploads

ENV BIDPILOT_DEBUG=false
ENV BIDPILOT_DATABASE_URL=sqlite+aiosqlite:///./data/bidpilot.db
ENV BIDPILOT_UPLOAD_DIR=./data/uploads
ENV BIDPILOT_LLM_PROVIDER=mock
ENV BIDPILOT_FRONTEND_DIST=/app/frontend_dist
ENV PORT=7860

EXPOSE 7860

CMD ["/app/modelscope_release/start.sh"]


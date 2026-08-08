FROM node:20-alpine AS frontend-build
WORKDIR /src/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY scripts/ ./scripts/
COPY modelscope_release/ ./modelscope_release/
COPY app.py ./app.py
COPY --from=frontend-build /src/frontend/dist ./frontend_dist

RUN chmod +x ./modelscope_release/start.sh && mkdir -p ./data/uploads

ENV BIDPILOT_DEBUG=false
ENV BIDPILOT_DATABASE_URL=sqlite+aiosqlite:///./data/bidpilot.db
ENV BIDPILOT_UPLOAD_DIR=./data/uploads
ENV BIDPILOT_LLM_PROVIDER=mock
ENV BIDPILOT_FRONTEND_DIST=/app/frontend_dist
ENV PORT=7860

EXPOSE 7860

CMD ["./modelscope_release/start.sh"]

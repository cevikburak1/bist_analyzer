FROM node:20-bookworm-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHON_BIN=/opt/venv/bin/python \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        curl \
        gcc \
        g++ \
        pkg-config \
        python3 \
        python3-pip \
        python3-venv \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN python3 -m venv /opt/venv \
    && pip install --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt

COPY dashboard/package*.json ./dashboard/
RUN cd dashboard && npm ci

COPY . .
RUN sed -i 's/\r$//' scripts/start-web.sh \
    && chmod +x scripts/start-web.sh \
    && cd dashboard \
    && npm run build

ENV NODE_ENV=production

EXPOSE 10000

CMD ["scripts/start-web.sh"]

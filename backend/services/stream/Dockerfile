FROM python:3.10-slim
RUN set -x && \
    if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
        sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources && \
        sed -i 's/security.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources; \
    fi && \
    (sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list || true) && \
    (sed -i 's/security.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list || true)

WORKDIR /app
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements/production.txt requirements.txt
RUN pip install --upgrade pip
RUN pip install --no-cache-dir  --default-timeout=1000 -r requirements.txt

# Copy backend source code
COPY backend backend
COPY config config

ENV PYTHONPATH=/app

EXPOSE 8003

CMD ["python", "backend/services/stream/main.py"]

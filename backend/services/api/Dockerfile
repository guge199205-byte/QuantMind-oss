FROM python:3.10-slim-bookworm
RUN set -x && \
    sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources && \
    sed -i 's/security.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources || \
    (sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list && \
     sed -i 's/security.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list)

WORKDIR /app
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements/production.txt requirements.txt
RUN pip install --upgrade pip
RUN pip install --no-cache-dir --default-timeout=1000 -r requirements.txt

# Copy backend source code
COPY backend backend
COPY config config

# 挂载开发目录，Dockerfile 仅保留基础环境
ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["python", "backend/services/api/main.py"]

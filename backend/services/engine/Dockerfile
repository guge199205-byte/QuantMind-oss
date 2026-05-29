# 使用官方 Python 3.10 slim 镜像
FROM python:3.10-slim-bookworm

RUN set -x && \
    sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources && \
    sed -i 's/security.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources || \
    (sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list && \
     sed -i 's/security.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list)

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    AI_IDE_PROJECT_ROOT=/app \
    ENGINE_ALLOW_MOCK_QLIB=false

WORKDIR /app

# 1. 准备依赖文件
COPY requirements/production.txt .
COPY requirements/ai.txt .

# 2. 【合层优化】安装编译工具 -> 安装 Python 依赖 -> 清理编译工具 (在同一个层内完成)
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/ && \
    apt-get update && apt-get install -y --no-install-recommends \
    curl gcc g++ cmake swig libgomp1 git && \
    pip install --upgrade pip setuptools wheel cython && \
    pip install --no-cache-dir -r production.txt && \
    if [ "$(uname -m)" = "x86_64" ]; then \
      pip install --no-cache-dir -r ai.txt; \
    else \
      grep -v '^pyqlib' ai.txt > ai.docker.txt && \
      pip install --no-cache-dir -r ai.docker.txt; \
    fi && \
    # 彻底清理编译依赖
    apt-get purge -y --auto-remove gcc g++ cmake swig git && \
    apt-get clean && rm -rf /var/lib/apt/lists/* && \
    # 清理 pip 缓存
    rm -rf /root/.cache/pip

# 3. 复制项目源代码 (利用 .dockerignore)
COPY backend/ backend/
COPY config/ config/

EXPOSE 8001

CMD ["python", "backend/services/engine/main.py"]

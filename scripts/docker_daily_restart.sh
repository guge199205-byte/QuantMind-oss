#!/bin/bash

# ==============================================================================
# QuantMind Docker 服务每日定时重启脚本
# 执行时间建议：每天凌晨 03:00
# 启动逻辑：先启动基础服务(Redis)，再启动业务核心，最后启动网关
# ==============================================================================

# 项目根目录路径 (根据实际部署路径调整)
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_FILE="${PROJECT_DIR}/logs/docker_restart.log"

mkdir -p "${PROJECT_DIR}/logs"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 开始每日例行服务重启..." >> "$LOG_FILE"

cd "$PROJECT_DIR" || exit 1

# 1. 停止所有服务
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 正在停止所有容器..." >> "$LOG_FILE"
docker-compose down >> "$LOG_FILE" 2>&1

# 2. 启动基础基础设施 (Redis)
# 注意：后端使用远程数据库 IP 139.199.75.121，故本地 postgres 不强制启动
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 启动基础服务: redis..." >> "$LOG_FILE"
docker-compose up -d redis >> "$LOG_FILE" 2>&1

# 等待 Redis 就绪
echo "等待 Redis 就绪..." >> "$LOG_FILE"
sleep 5

# 3. 启动核心业务集群
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 启动核心业务集群..." >> "$LOG_FILE"
# 按依赖关系分步或批量启动
docker-compose up -d api-server trade-core stream-gateway >> "$LOG_FILE" 2>&1
sleep 5

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 启动计算引擎与 Worker..." >> "$LOG_FILE"
docker-compose up -d engine-compute engine-worker >> "$LOG_FILE" 2>&1
sleep 5

# 4. 最后启动 API 网关
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 启动入口网关: nginx-gateway..." >> "$LOG_FILE"
docker-compose up -d nginx-gateway >> "$LOG_FILE" 2>&1

# 5. 清理过期镜像和残留卷 (可选，保持磁盘整洁)
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 正在清理系统残留..." >> "$LOG_FILE"
docker system prune -f >> "$LOG_FILE" 2>&1

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 所有服务重启任务完成。" >> "$LOG_FILE"
echo "------------------------------------------------------" >> "$LOG_FILE"

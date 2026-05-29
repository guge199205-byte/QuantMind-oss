#!/bin/bash
# QuantMind 一键部署脚本
# 用法: chmod +x setup.sh && ./setup.sh

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${CYAN}[INFO]${NC} $1"; }
ok()    { echo -e "${GREEN}[OK]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

echo ""
echo "========================================="
echo "  QuantMind 一键部署"
echo "========================================="
echo ""

# -------------------------------------------
# 1. 环境检查
# -------------------------------------------
info "检查系统环境..."

if ! command -v docker &>/dev/null; then
    error "未检测到 Docker，请先安装: https://docs.docker.com/get-docker/"
fi

if ! docker compose version &>/dev/null && ! docker-compose version &>/dev/null; then
    error "未检测到 Docker Compose，请先安装: https://docs.docker.com/compose/install/"
fi

DOCKER_VERSION=$(docker version --format '{{.Server.Version}}' 2>/dev/null || echo "unknown")
ok "Docker ${DOCKER_VERSION}"

# 检测 compose 命令
if docker compose version &>/dev/null; then
    COMPOSE_CMD="docker compose"
else
    COMPOSE_CMD="docker-compose"
fi
ok "Compose: ${COMPOSE_CMD}"

# -------------------------------------------
# 2. 配置 .env
# -------------------------------------------
if [ -f .env ]; then
    warn ".env 文件已存在，跳过生成（如需重新配置请先删除 .env）"
else
    info "生成 .env 配置文件..."

    # 生成随机密钥
    SECRET_KEY=$(openssl rand -hex 32 2>/dev/null || head -c 64 /dev/urandom | od -An -tx1 | tr -d ' \n' | head -c 64)
    JWT_SECRET=$(openssl rand -hex 32 2>/dev/null || head -c 64 /dev/urandom | od -An -tx1 | tr -d ' \n' | head -c 64)
    DB_PASSWORD=$(openssl rand -base64 16 2>/dev/null | tr -dc 'a-zA-Z0-9' | head -c 20 || echo "quantmind$(date +%s)")

    cp .env.example .env

    # 替换默认值
    sed -i "s/CHANGE_ME_GENERATE_YOUR_OWN_SECRET_KEY/${SECRET_KEY}/" .env
    sed -i "s/CHANGE_ME_GENERATE_YOUR_OWN_JWT_SECRET/${JWT_SECRET}/" .env
    sed -i "s/CHANGE_ME_DB_PASSWORD/${DB_PASSWORD}/" .env

    ok ".env 已生成（密钥已随机化）"
fi

# -------------------------------------------
# 3. 创建必要目录
# -------------------------------------------
info "创建数据目录..."
mkdir -p data db models logs strategy_templates user_pools_local
ok "目录就绪"

# -------------------------------------------
# 4. 构建镜像
# -------------------------------------------
info "构建 Docker 镜像（首次约 5-15 分钟）..."
${COMPOSE_CMD} build --progress=plain
ok "镜像构建完成"

# -------------------------------------------
# 5. 启动服务
# -------------------------------------------
info "启动所有服务..."
${COMPOSE_CMD} up -d

# 等待核心服务就绪
info "等待服务就绪..."
MAX_WAIT=120
ELAPSED=0
while [ $ELAPSED -lt $MAX_WAIT ]; do
    if ${COMPOSE_CMD} ps quantmind 2>/dev/null | grep -q "healthy\|running"; then
        break
    fi
    sleep 3
    ELAPSED=$((ELAPSED + 3))
    echo -n "."
done
echo ""

if [ $ELAPSED -ge $MAX_WAIT ]; then
    warn "服务启动超时（${MAX_WAIT}s），请检查日志: ${COMPOSE_CMD} logs quantmind"
else
    ok "核心服务已启动"
fi

# -------------------------------------------
# 6. 初始化（RD-Agent + 数据检查）
# -------------------------------------------
info "运行初始化脚本..."
${COMPOSE_CMD} exec -T quantmind bash /app/scripts/setup/init.sh --no-data-sync 2>/dev/null || warn "初始化脚本执行异常，请手动运行: docker exec quantmind bash /app/scripts/setup/init.sh"

# -------------------------------------------
# 7. 显示结果
# -------------------------------------------
echo ""
echo "========================================="
echo -e "  ${GREEN}QuantMind 部署完成！${NC}"
echo "========================================="
echo ""
echo "  访问地址:"
echo "    Web 前端:  http://localhost:3000"
echo "    API:       http://localhost:8000"
echo "    Huntly:    http://localhost:8090"
echo "    RSSHub:    http://localhost:1200"
echo ""
echo "  默认管理员:"
echo "    用户名: admin"
echo "    密码:   admin123"
echo ""
echo "  常用命令:"
echo "    查看状态:  ${COMPOSE_CMD} ps"
echo "    查看日志:  ${COMPOSE_CMD} logs -f quantmind"
echo "    停止服务:  ${COMPOSE_CMD} down"
echo "    重启服务:  ${COMPOSE_CMD} restart"
echo ""
echo "  下一步:"
echo "    1. 登录后修改默认密码"
echo "    2. 在 .env 中配置 AI API Key（DeepSeek/Qwen）"
echo "    3. 下载数据包: https://oss.quantmindai.cn/data-download.html"
echo "    4. 详细文档: docs/部署指南.md"
echo ""

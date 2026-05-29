#!/usr/bin/env bash
# =============================================================================
# scripts/build/build_training_image.sh
#
# 构建训练 Docker 镜像并推送到腾讯云 TCR，自动将 tag@digest 写入服务器 .env，
# 确保下次 BatchCompute 任务使用确定性镜像版本。
#
# 用法：
#   ./scripts/build/build_training_image.sh [TAG]
#
#   TAG  可选，默认自动生成 training-YYYYMMDD-HHMMSS
#
# 依赖：
#   - 本机或服务器已登录 TCR（docker login ccr.ccs.tencentyun.com）
#   - 必须在 x86 环境运行（本机 ARM 不支持直接构建 x86 镜像）
#   - 服务器 SSH 别名 quantmind-server 已配置
#   - 根目录 .env 中存在 TCR_REGISTRY / TCR_USERNAME / TCR_PASSWORD
# =============================================================================
set -euo pipefail

# ── 加载 .env ──────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

if [[ -f "$ROOT_DIR/.env" ]]; then
    # 只导出 TCR_* 变量，不污染整个 shell 环境
    set -a
    # shellcheck disable=SC1091
    source <(grep -E '^TCR_' "$ROOT_DIR/.env")
    set +a
fi

TCR_REGISTRY="${TCR_REGISTRY:-ccr.ccs.tencentyun.com}"
TCR_USERNAME="${TCR_USERNAME:-100003290041}"
TCR_PASSWORD="${TCR_PASSWORD:-}"
REPO="${TCR_REGISTRY}/tcb-100003290041-ufqf/quantmind"
TAG="${1:-training-$(date +%Y%m%d-%H%M%S)}"
FULL_IMAGE="${REPO}:${TAG}"
SERVER_ENV_PATH="/home/quantmind/.env"

echo "=============================================="
echo "  QuantMind Training Image Build & Push"
echo "=============================================="
echo "  镜像：${FULL_IMAGE}"
echo "  服务器 .env：${SERVER_ENV_PATH}"
echo "----------------------------------------------"

# ── 登录 TCR ───────────────────────────────────────────────────────────────────
echo "[1/4] 登录 TCR..."
echo "$TCR_PASSWORD" | docker login "$TCR_REGISTRY" \
    --username="$TCR_USERNAME" \
    --password-stdin
echo "      ✅ 登录成功"

# ── 构建镜像 ───────────────────────────────────────────────────────────────────
echo "[2/4] 构建镜像..."
docker build \
    -f "$ROOT_DIR/docker/Dockerfile.training" \
    -t "$FULL_IMAGE" \
    "$ROOT_DIR"
echo "      ✅ 构建完成"

# ── 推送并捕获 digest ──────────────────────────────────────────────────────────
echo "[3/4] 推送镜像并获取 digest..."
PUSH_OUTPUT=$(docker push "$FULL_IMAGE" 2>&1)
echo "$PUSH_OUTPUT"

# 从 push 输出中提取 digest（格式：digest: sha256:xxx size: yyy）
DIGEST=$(echo "$PUSH_OUTPUT" | grep -oP 'digest: \Ksha256:[a-f0-9]+' | tail -1)

if [[ -z "$DIGEST" ]]; then
    # 备用方案：通过 docker inspect 从本地获取
    DIGEST=$(docker inspect --format='{{index .RepoDigests 0}}' "$FULL_IMAGE" \
        2>/dev/null | grep -oP 'sha256:[a-f0-9]+' || true)
fi

if [[ -z "$DIGEST" ]]; then
    echo "⚠️  未能获取 digest，将仅使用 tag（不影响推送）"
    IMAGE_REF="$FULL_IMAGE"
else
    IMAGE_REF="${FULL_IMAGE}@${DIGEST}"
    echo "      ✅ digest: ${DIGEST}"
fi

echo "      镜像引用: ${IMAGE_REF}"

# ── 写入服务器 .env ────────────────────────────────────────────────────────────
echo "[4/4] 更新服务器 .env → TRAINING_IMAGE..."

# 通过 SSH 更新远程 .env（若 TRAINING_IMAGE 行存在则替换，否则追加）
ssh quantmind-server bash << EOF
if grep -q '^TRAINING_IMAGE=' "${SERVER_ENV_PATH}"; then
    sed -i "s|^TRAINING_IMAGE=.*|TRAINING_IMAGE=${IMAGE_REF}|" "${SERVER_ENV_PATH}"
    echo "      已更新 TRAINING_IMAGE"
else
    echo "" >> "${SERVER_ENV_PATH}"
    echo "# 训练镜像（由 build_training_image.sh 自动更新）" >> "${SERVER_ENV_PATH}"
    echo "TRAINING_IMAGE=${IMAGE_REF}" >> "${SERVER_ENV_PATH}"
    echo "      已新增 TRAINING_IMAGE"
fi
grep '^TRAINING_IMAGE=' "${SERVER_ENV_PATH}"
EOF

echo "----------------------------------------------"
echo "  ✅ 完成！"
echo ""
echo "  下一步：重新部署 api 容器使环境变量生效"
echo "  cd /home/quantmind && ./deploy_live.sh"
echo "=============================================="

#!/bin/bash
# QuantMind 快速部署脚本
# 在服务器上运行此脚本即可完成部署

set -euo pipefail

echo "========================================"
echo "  QuantMind 快速部署"
echo "========================================"

# 检查 root 权限
if [[ $EUID -ne 0 ]]; then
    echo "错误: 需要 root 权限"
    echo "请使用: sudo bash $0"
    exit 1
fi

# 下载部署脚本（使用临时目录，避免提前占用 /opt/quantmind）
TMP_DEPLOY_DIR="$(mktemp -d /tmp/quantmind-deploy.XXXXXX)"
DEPLOY_SCRIPT="$TMP_DEPLOY_DIR/deploy.sh"
DEPLOY_URL="https://raw.githubusercontent.com/guge199205-byte/QuantMind-oss/main/deploy/deploy.sh"
EXPECTED_SHA256="${QUANTMIND_DEPLOY_SHA256:-}"
cleanup() {
    rm -rf "$TMP_DEPLOY_DIR"
}
trap cleanup EXIT

echo "下载部署脚本..."
curl -fsSL "$DEPLOY_URL" -o "$DEPLOY_SCRIPT"

if [[ -n "$EXPECTED_SHA256" ]]; then
    ACTUAL_SHA256="$(sha256sum "$DEPLOY_SCRIPT" | awk '{print $1}')"
    if [[ "$ACTUAL_SHA256" != "$EXPECTED_SHA256" ]]; then
        echo "错误: deploy.sh 校验失败"
        echo "期望: $EXPECTED_SHA256"
        echo "实际: $ACTUAL_SHA256"
        exit 1
    fi
    echo "deploy.sh 校验通过"
else
    echo "警告: 未设置 QUANTMIND_DEPLOY_SHA256，已跳过 deploy.sh 完整性校验"
fi

# 添加执行权限
chmod +x "$DEPLOY_SCRIPT"

# 执行部署（交互式）
echo "开始部署..."
bash "$DEPLOY_SCRIPT"

#!/bin/bash
# 安装 QuantMind 数据平台每日校验 cron（宿主机）
# 用法：sudo bash scripts/ops/install_data_validation_cron.sh

set -e

LOG_DIR=/var/log/quantmind
LOG_FILE="$LOG_DIR/data_validation.log"
CONTAINER=${QM_CONTAINER:-quantmind}

mkdir -p "$LOG_DIR"
touch "$LOG_FILE"
chmod 644 "$LOG_FILE"

CRON_LINE="30 18 * * * docker exec $CONTAINER python -m backend.services.engine.data_platform.cron.daily_validation --market ALL --sample 50 >> $LOG_FILE 2>&1"

# 去重写入
(crontab -l 2>/dev/null | grep -v "data_platform.cron.daily_validation"; echo "$CRON_LINE") | crontab -

echo "✅ cron 已安装："
echo "   $CRON_LINE"
echo "日志：$LOG_FILE"

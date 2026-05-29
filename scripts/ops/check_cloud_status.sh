#!/bin/bash
# ==============================================================================
# QuantMind 云端状态一键巡检脚本 (GCP/GKE Edition)
# 用途: 快速检测后端核心集群、Runner及数据库隧道的健康状态
# ==============================================================================

NAMESPACE="quantmind"
PROJECT_ID=$(gcloud config get-value project)

echo "======================================================================"
echo "🚀 QuantMind 生产环境巡检报告 | Project: $PROJECT_ID"
echo "🕒 时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "======================================================================"

# 1. 检查 Pod 运行状态
echo -e "
📦 [1/4] 后端容器组状态:"
kubectl get pods -n $NAMESPACE -o wide | grep -v "NAME" | awk '{print "  - "$1 " ["$3"] Restarts: "$4}'

# 2. 检查核心服务资源占用 (需 Metrics Server)
echo -e "
📊 [2/4] 资源消耗实时快照 (Top):"
kubectl top pods -n $NAMESPACE --no-headers 2>/dev/null | awk '{print "  - "$1 ": CPU "$2", MEM "$3}' || echo "  ⚠️  Metrics Server 尚未就绪，跳过。"

# 3. 核心链路与 API 可达性
echo -e "
🌐 [3/4] 公网 Ingress 入口测试:"
INGRESS_IP=$(kubectl get ingress quantmind-ingress -n $NAMESPACE -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null)
if [ -z "$INGRESS_IP" ]; then
    echo "  ❌ 无法获取 Ingress IP，负载均衡器可能正在初始化。"
else
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://$INGRESS_IP/health --max-time 3)
    if [ "$HTTP_CODE" == "200" ]; then
        echo "  ✅ API 正常响应 (HTTP 200) | IP: $INGRESS_IP"
    else
        echo "  ⚠️ API 响应异常 (HTTP $HTTP_CODE) | IP: $INGRESS_IP"
    fi
fi

# 4. 最近关键错误审计 (最近 100 行)
echo -e "
🚨 [4/4] 最近 5 分钟异常监控 (Structured Logs Search):"
ERROR_COUNT=$(kubectl logs -n $NAMESPACE -l app=quantmind-runner --tail=100 --since=5m | grep -i "ERROR" | wc -l)
if [ "$ERROR_COUNT" -gt 0 ]; then
    echo "  🔥 警告: 发现 $ERROR_COUNT 条 Runner 异常日志！"
    kubectl logs -n $NAMESPACE -l app=quantmind-runner --tail=50 | grep -i "ERROR" | head -n 5
else
    echo "  ✅ 链路日志清洁，无挂起异常。"
fi

echo -e "
======================================================================"
echo "💡 提示: 运行 'kubectl logs -f deployment/quantmind-runner-default -n quantmind' 查看实时信号流。"
echo "======================================================================"

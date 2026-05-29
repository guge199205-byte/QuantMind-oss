# GKE 测试发布 Runbook

本文档固化 QuantMind 后端 4 核心服务在 GKE + Cloud SQL PostgreSQL 上的测试发布流程。

适用范围：
- `quantmind-api`
- `quantmind-engine`
- `quantmind-trade`
- `quantmind-stream`

对应模板：
- [k8s/quantmind-test-release.yaml](/Users/qusong/git/quantmind/k8s/quantmind-test-release.yaml)

对应脚本：
- [backend/scripts/gke_test_release.sh](/Users/qusong/git/quantmind/backend/scripts/gke_test_release.sh)
- [backend/scripts/gke_smoke_check.sh](/Users/qusong/git/quantmind/backend/scripts/gke_smoke_check.sh)

## 前置条件

本机要求：
- 已安装并登录 `gcloud`
- 已安装 `kubectl`
- 已安装 Docker，且已启用 `buildx`
- 已存在项目根目录 `.venv`

GCP 要求：
- 已启用 `container.googleapis.com`
- 已启用 `artifactregistry.googleapis.com`
- 已启用 `sqladmin.googleapis.com`

## 推荐环境变量

```bash
export PROJECT_ID="your-gcp-project"
export GKE_CLUSTER="quantmind-test-cluster"
export GKE_ZONE="asia-east1-a"
export REGISTRY_LOCATION="asia-east1"
export ARTIFACT_REPO="quantmind-repo"
export NAMESPACE="quantmind-test"
export IMAGE_TAG="latest"
export TRADE_IMAGE_TAG="slim-20260306"

export DB_NAME="quantmind"
export DB_USER="admin"
export DB_PASSWORD="admin123"
export SQL_INSTANCE_CONNECTION_NAME="your-project:asia-east1:quantmind-test-pg"

export INTERNAL_CALL_SECRET="quantmind_internal_secret_2026"
export SECRET_KEY="replace-with-real-secret"
export JWT_SECRET_KEY="replace-with-real-jwt-secret"
```

说明：
- `SECRET_KEY` 和 `JWT_SECRET_KEY` 建议显式传入；若不传，脚本会自动生成随机值。
- 正式环境不要继续使用文档中的示例密码与示例内部密钥。
- `TRADE_IMAGE_TAG` 不传时默认回退到 `IMAGE_TAG`；如需锁定瘦身版 `trade` 镜像，单独设置即可。

## 1. 构建并推送镜像

推荐使用 `linux/amd64` 构建，避免本机为 Apple Silicon 时推送出不可在 GKE 节点运行的镜像。

```bash
gcloud auth configure-docker "${REGISTRY_LOCATION}-docker.pkg.dev" --quiet

docker buildx build --platform linux/amd64 \
  -f backend/services/api/Dockerfile \
  -t "${REGISTRY_LOCATION}-docker.pkg.dev/${PROJECT_ID}/${ARTIFACT_REPO}/quantmind-api:${IMAGE_TAG}" \
  --push .

docker buildx build --platform linux/amd64 \
  -f backend/services/engine/Dockerfile \
  -t "${REGISTRY_LOCATION}-docker.pkg.dev/${PROJECT_ID}/${ARTIFACT_REPO}/quantmind-engine:${IMAGE_TAG}" \
  --push .

docker buildx build --platform linux/amd64 \
  -f backend/services/trade/Dockerfile \
  -t "${REGISTRY_LOCATION}-docker.pkg.dev/${PROJECT_ID}/${ARTIFACT_REPO}/quantmind-trade:${TRADE_IMAGE_TAG:-$IMAGE_TAG}" \
  --push .

docker buildx build --platform linux/amd64 \
  -f backend/services/stream/Dockerfile \
  -t "${REGISTRY_LOCATION}-docker.pkg.dev/${PROJECT_ID}/${ARTIFACT_REPO}/quantmind-stream:${IMAGE_TAG}" \
  --push .
```

## 2. 初始化 Cloud SQL PostgreSQL

创建用户与数据库后，将 [db/20260305.sql](/Users/qusong/git/quantmind/db/20260305.sql) 导入目标库。

推荐方式：
- 上传 SQL 文件到 GCS
- 使用 `gcloud sql import sql` 导入

示例：

```bash
gsutil cp db/20260305.sql "gs://${PROJECT_ID}-quantmind-test-release/20260305.sql"

gcloud sql import sql quantmind-test-pg \
  "gs://${PROJECT_ID}-quantmind-test-release/20260305.sql" \
  --database="${DB_NAME}" \
  --quiet
```

注意：
- Cloud SQL 实例服务账号需要对 GCS bucket 拥有 `objectViewer`
- GKE 节点服务账号需要具备 `roles/cloudsql.client`

## 3. 发布到 GKE

执行：

```bash
backend/scripts/gke_test_release.sh
```

脚本会自动完成：
- 获取集群凭据
- 渲染 [k8s/quantmind-test-release.yaml](/Users/qusong/git/quantmind/k8s/quantmind-test-release.yaml)
- `kubectl apply`
- 等待 5 个 Deployment 全部就绪

镜像 tag 规则：
- `quantmind-api / quantmind-engine / quantmind-stream` 使用 `IMAGE_TAG`
- `quantmind-trade` 优先使用 `TRADE_IMAGE_TAG`，未设置时回退到 `IMAGE_TAG`

如只想预览渲染结果：

```bash
RENDER_ONLY=1 backend/scripts/gke_test_release.sh
```

如只想 `apply` 而不等待 rollout：

```bash
SKIP_ROLLOUT=1 backend/scripts/gke_test_release.sh
```

渲染产物输出到：
- `k8s/.rendered-quantmind-test-release.yaml`

## 4. 发布后 Smoke

执行：

```bash
backend/scripts/gke_smoke_check.sh
```

脚本会校验：
- 4 个 `/health`
- 4 个 `/metrics`
- `api -> trade` 代理不返回 `503`
- `api -> engine` 代理不返回 `503`
- `stream /ws` 握手与 `ping/pong`

## 5. 建议验收标准

- `kubectl get deploy -n ${NAMESPACE}` 显示全部 `AVAILABLE`
- `kubectl get pods -n ${NAMESPACE}` 无 `CrashLoopBackOff` / `ImagePullBackOff`
- 4 个 `/health` 都返回 `healthy`
- `api -> trade` 与 `api -> engine` 都返回业务侧受控响应，而不是 `5xx`
- `stream` WebSocket 返回 `welcome` 与 `pong`

## 6. 常见问题

### 0. Trade 首启内存峰值

`quantmind-trade` 在正式镜像首次冷启动时可能出现明显内存峰值。当前模板基线已调整为：
- `requests.memory=512Mi`
- `limits.memory=2Gi`
- `MALLOC_ARENA_MAX=2`

如果再次出现 `OOMKilled`，优先检查：
- 是否误把旧模板中的 `1Gi` limit 带回去了
- 节点是否存在镜像首次拉取 + 解压阶段的资源抖动

### 1. Pod `ImagePullBackOff`

优先检查：
- 镜像是否已推送到 Artifact Registry
- `IMAGE_TAG` 是否正确
- `quantmind-trade` 如使用单独版本，确认 `TRADE_IMAGE_TAG` 与已推送 tag 一致
- GKE 节点所在项目是否能拉取同项目镜像

### 2. Pod `Pending` 且提示 `Insufficient cpu`

说明测试集群节点资源不够。处理方式：

```bash
gcloud container clusters resize "${GKE_CLUSTER}" \
  --zone "${GKE_ZONE}" \
  --node-pool default-pool \
  --num-nodes 2 \
  --quiet
```

### 3. Cloud SQL 连接失败

优先检查：
- `SQL_INSTANCE_CONNECTION_NAME` 是否正确
- 节点服务账号是否具备 `roles/cloudsql.client`
- Pod 中 `cloud-sql-proxy` 是否正常启动

### 4. Stream WebSocket 返回 403

当前 `/ws` 需要显式鉴权头或查询参数。脚本已使用：
- `x-user-id`
- `x-tenant-id`
- `tenant_id`
- `user_id`

## 7. 回滚

```bash
kubectl rollout undo deployment/quantmind-api -n "${NAMESPACE}"
kubectl rollout undo deployment/quantmind-engine -n "${NAMESPACE}"
kubectl rollout undo deployment/quantmind-trade -n "${NAMESPACE}"
kubectl rollout undo deployment/quantmind-stream -n "${NAMESPACE}"
```

如需整环境清理：

```bash
kubectl delete namespace "${NAMESPACE}"
```

## 8. 说明

这份 runbook 固化的是“测试发布”流程，重点是：
- 能稳定把 4 服务部署到 GKE
- 能在真实 Cloud SQL/Redis/Service 网络下完成最小可用验证

它不是最终的正式生产发布 SOP。进入正式生产前，仍建议继续补：
- Ingress / 域名 / HTTPS
- 监控告警联通性检查
- 灰度发布与回滚自动化
- 独立的 migration / bootstrap 流程

# Alertmanager Webhook 服务

Alertmanager Webhook 是 QuantMind 平台的**监控运维接收端**。它主要用于接收、解析并记录来自 Prometheus Alertmanager 的告警通知。

## 核心定位

该服务作为一个中间件，将 Prometheus 发现的底层系统异常（如基础设施故障、中间件不可用等）转化为系统可读的结构化数据，并为后续的自动修复（如哨兵切换）或人工介入提供数据支持。

## 主要功能

*   **告警接收**：提供多个 HTTP POST 端点，接收 Alertmanager 推送的 JSON 报文。
*   **结构化解析**：由 `AlertProcessor` 提取告警名称、严重程度、受影响组件、摘要及详细描述。
*   **分级处理**：
    *   **普通告警**：记录日志并存储到内存历史记录中。
    *   **严重告警 (Critical)**：触发特殊的处理逻辑，如集成短信通知、资源清理或故障转移。
*   **组件识别**：支持针对 `postgresql`、`redis`、`system` 等核心组件的定制化处理。
*   **状态统计**：提供实时 API，查看系统当前活跃告警及历史告警频率。

## 技术选型

*   **框架**：Flask
*   **日志**：同步记录到 `logs/alertmanager-webhook.log`
*   **端口**：默认运行在 `8016` 端口

## API 接口

### 1. 默认告警接收
*   **路径**：`/webhook/alerts`
*   **方法**：`POST`
*   **用途**：通用的告警通知入口。

### 2. 严重告警接收
*   **路径**：`/webhook/critical`
*   **方法**：`POST`
*   **用途**：当告警级别为 `critical` 时，Alertmanager 应路由至此端点以触发最高优先级的处理逻辑。

### 3. 统计信息
*   **路径**：`/stats`
*   **方法**：`GET`
*   **返回**：最近 10 条告警历史及各告警类型的累计计数。

## 部署说明

该服务通常运行在内部管理网络中，不对外网开放。配置 Alertmanager 时，请在 `alertmanager.yml` 中添加如下配置：

```yaml
receivers:
- name: 'quantmind-webhook'
  webhook_configs:
  - url: 'http://<host>:8016/webhook/alerts'
```

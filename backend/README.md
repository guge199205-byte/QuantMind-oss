# QuantMind 后端核心服务集群

本项目后端采用收敛后的架构，由 4 个核心服务集群组成，通过核心边界进行物理隔离与资源优化。

## 服务概览 (V2 Consolidated)

| 服务名称 | 端口 | 代码路径 | 整合模块 | 文档 |
| :--- | :--- | :--- | :--- | :--- |
| **quantmind-api** | 8000 | `services/api/` | 用户、社区、通知、管理、静态查询、运维回调 | [README](services/api/README.md) |
| **quantmind-trade** | 8002 | `services/trade/` | 订单管理、持仓核算、模拟撮合、风控核心 | [README](services/trade/README.md) |
| **quantmind-engine** | 8001 | `services/engine/` | AI 策略生成、模型推理、Qlib 回测引擎 | [README](services/engine/README.md) |
| **quantmind-stream** | 8003 | `services/stream/` | 实时行情接入、WebSocket 高并发推送 | [README](services/stream/README.md) |

## 核心架构原则

1.  **统一边界**：根据“业务、资金、算力、I/O”四个维度进行物理隔离。
2.  **数据隔离**：各服务拥有独立的逻辑边界，严禁跨服务直接操作对方的私有状态。
3.  **高性能通信**：集群内采用函数级调用，集群间采用 REST API 或消息队列。
4.  **资源配额**：针对计算引擎等耗能大户，在 Docker 层实施严格的 CPU/内存限制。

## 开发指南

请参考项目根目录的 [GEMINI.md](../GEMINI.md) 获取详细的开发规范、环境设置及测试说明。

## 共享模块

*   `shared/`：包含数据库管理器、Redis 客户端、统一配置加载、日志规范等跨服务复用的核心代码。详见 [shared/README.md](shared/README.md)。
*   `shared/strategy_storage.py`：**统一策略存储服务**（PG + COS），是所有策略 CRUD 的唯一入口。
*   `shared/schema_registry.py`：统一维护 `services/*` 的 SQLAlchemy schema 注册清单。

## Schema 巡检

```bash
source .venv/bin/activate
python backend/scripts/schema_registry_audit.py
# 可选：同时校验数据库缺失表
python backend/scripts/schema_registry_audit.py --check-db
```

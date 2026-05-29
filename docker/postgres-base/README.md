# PostgreSQL Base Image

`quantmind-postgres-base` 是 QuantMind 的基础数据库镜像模板，启动时会自动初始化核心表结构，并恢复 `db/20260303.sql` 备份。

## 包含内容

- QMT 核心表：`qmt_account_assets` / `qmt_positions` / `qmt_orders` / `qmt_trades` / `qmt_sync_logs`
- 选股与行情表：`stock_daily`（含默认分区 + 当月分区）/ `stock_screener_snapshot`
- 常用扩展：`uuid-ossp`、`pg_trgm`
- 基础备份恢复：`db/20260303.sql`（镜像构建时打包，首次启动自动导入）

## 构建

```bash
docker build -f docker/postgres-base/Dockerfile -t quantmind-postgres-base:latest .
```

## 运行示例

```bash
docker run -d \
  --name quantmind-postgres \
  -e POSTGRES_USER=quantmind \
  -e POSTGRES_PASSWORD=change_me \
  -e POSTGRES_DB=quantmind \
  -p 5432:5432 \
  quantmind-postgres-base:latest
```

首次启动会执行 `/docker-entrypoint-initdb.d` 下 SQL；已有数据卷时不会重复初始化。

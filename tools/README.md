# tools

工具脚本说明（按需扩展）。

## backfill_pe_ttm.py

用途：补全 PostgreSQL `stock_daily.pe_ttm` 空值（同花顺 iFinD HTTP API）。

要点：
- 读取项目根目录 .env（环境变量优先生效）
- 使用 `IFIND_ACCESS_TOKEN`；若缺省则用 `IFIND_REFRESH_TOKEN` 换取
- 仅更新 `pe_ttm IS NULL` 的记录

示例：
- 仅处理最近 5 个交易日（不限制则去掉 `--limit-dates`）
- 每批 50 只股票

命令：
- `python tools/backfill_pe_ttm.py --limit-dates 5 --batch-size 50`
- 若包含指数代码且需补全指数口径，可指定：
	- `python tools/backfill_pe_ttm.py --indicator-index <INDEX_PE_INDICATOR>`

## stock_list.json

用途：实时查询脚本的股票池。

更新来源：Akshare `stock_info_a_code_name()`（A 股全量代码）。

## real_time_pe_ttm_to_db.py

用途：按股票列表逐只查询 iFinD `pe_ttm` 并写入 `stock_daily`，确保上一只写入成功后再处理下一只。

示例：
- 全量执行：`python tools/real_time_pe_ttm_to_db.py`
- 从第 1000 只开始处理 200 只：`python tools/real_time_pe_ttm_to_db.py --start-index 1000 --limit 200`
- 并发模式（方案3）：`python tools/real_time_pe_ttm_to_db.py --mode async --concurrency 50 --write-batch 500`

## simple_index_update.py / simple_stock_update.py

用途：使用 AkShare 同步指数与股票基础数据。

数据库约束：
- 仅支持 PostgreSQL 连接（`postgresql+psycopg2://...`）
- 读取 `DB_HOST/DB_PORT/DB_USER/DB_PASSWORD/DB_NAME` 环境变量

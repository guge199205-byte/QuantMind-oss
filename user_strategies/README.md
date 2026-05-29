# 用户策略存储目录

本目录用于存放智能模块生成和用户创建的量化交易策略。

## 目录结构

```
user_strategies/
├── ai_generated/          # AI智能模块自动生成的策略
│   ├── {strategy_id}.py   # 策略文件（命名格式: strategy_YYYYMMDD_HHMMSS_id.py）
│   └── {strategy_id}.json # 策略元数据
├── manual_created/        # 用户手动创建的策略
│   ├── my_strategy_v1.py
│   └── custom_logic.py
├── templates/             # 策略模板
│   ├── momentum_template.py
│   ├── mean_reversion_template.py
│   ├── ai_rebalance_template.py    # AI 智能调仓策略（支持双模式）
│   └── qlib_topk_template.py
└── archived/              # 已归档的策略
    └── old_strategies/
```

## 策略文件规范

### 1. Python 策略文件 (.py)

每个策略文件必须包含以下结构：

```python
"""
策略名称: 双均线交叉策略
策略描述: 基于短期和长期均线交叉信号进行交易
创建时间: 2026-01-15
创建方式: AI生成 / 手动创建
"""

class Strategy:
    def __init__(self, context):
        self.short_period = 5
        self.long_period = 20

    def on_bar(self, context, bars):
        # 策略逻辑
        pass
```

Qlib 策略模板需要提供 `STRATEGY_CONFIG`（或 `get_strategy_config()`）：

```python
STRATEGY_CONFIG = {
    "class": "TopkDropoutStrategy",
    "module_path": "qlib.contrib.strategy.signal_strategy",
    "kwargs": {
        "signal": "<PRED>",
        "topk": 50,
        "n_drop": 5,
    },
}
```

### 2. 策略元数据文件 (.json)

与策略文件同名的 JSON 文件，存储策略元信息：

```json
{
  "id": "strategy_20260115_143022_abc123",
  "name": "双均线交叉策略",
  "description": "基于短期和长期均线交叉信号进行交易",
  "author": "AI智能模块",
  "created_at": "2026-01-15T14:30:22Z",
  "updated_at": "2026-01-15T14:30:22Z",
  "version": "1.0.0",
  "category": "趋势跟踪",
  "tags": ["均线", "技术指标", "趋势"],
  "parameters": {
    "short_period": {
      "type": "int",
      "default": 5,
      "min": 3,
      "max": 20,
      "description": "短期均线周期"
    },
    "long_period": {
      "type": "int",
      "default": 20,
      "min": 10,
      "max": 100,
      "description": "长期均线周期"
    }
  },
  "backtest_results": {
    "latest_run": "2026-01-15T15:00:00Z",
    "sharpe_ratio": 1.85,
    "max_drawdown": -0.12,
    "total_return": 0.35
  }
}
```

## 使用方式

### 1. 快速回测服务加载策略

快速回测服务会自动扫描此目录中的策略文件，并在个人中心展示：

```typescript
// 前端调用示例
import { loadUserStrategies } from '@/services/qlib/qlibBacktestService';

const strategies = await loadUserStrategies();
```

### 2. AI 智能模块生成策略

智能模块生成策略后，自动保存到 `ai_generated/` 目录：

```python
# 后端保存示例
strategy_id = f"strategy_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
strategy_path = f"user_strategies/ai_generated/{strategy_id}.py"

with open(strategy_path, 'w', encoding='utf-8') as f:
    f.write(generated_strategy_code)
```

### 3. 策略导入导出

- **导出**: 复制 `.py` 和 `.json` 文件
- **导入**: 将策略文件放入对应目录即可自动识别

## 权限管理

- **AI智能模块**: 读写权限（`ai_generated/`）
- **用户**: 全部目录读写权限
- **快速回测服务**: 全部目录只读权限

## 注意事项

1. **文件命名**: 使用英文和下划线，避免特殊字符
2. **代码安全**: 策略代码会在沙箱环境中执行
3. **版本控制**: 建议为重要策略创建 Git 版本
4. **备份策略**: 定期备份 `user_strategies/` 目录
5. **归档旧策略**: 不再使用的策略移动到 `archived/` 目录

## 示例策略

参考 `templates/` 目录中的模板策略开始创建。

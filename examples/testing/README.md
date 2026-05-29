# Test Strategy Examples

This directory contains example strategies from various platforms for testing the AI Strategy Conversion feature.

## Files

### 1. `joinquant_example.py` - 聚宽平台示例
- **Platform:** JoinQuant
- **Features:**
  - Uses `initialize(context)` and `handle_data(context, data)`
  - Contains `set_universe`, `order_target_percent`
  - 5-day momentum strategy
- **Expected Detection:** Should auto-detect as "joinquant"

### 2. `ricequant_example.py` - 米筐平台示例
- **Platform:** RiceQuant
- **Features:**
  - Uses `init(context)` and `scheduler.run_daily`
  - Contains `history_bars`, `order_target_percent`
  - Rebalancing strategy
- **Expected Detection:** Should auto-detect as "ricequant"

### 3. `backtrader_example.py` - Backtrader平台示例
- **Platform:** Backtrader
- **Features:**
  - Inherits from `bt.Strategy`
  - Uses `bt.indicators.SimpleMovingAverage`
  - Moving average crossover strategy
- **Expected Detection:** Should auto-detect as "backtrader"

## How to Test

### In Quick Backtest Module
1. Navigate to **回测中心 → 快速回测**
2. Click **选择策略文件**
3. Upload one of the example files
4. You should see an **orange warning** indicating non-Qlib format
5. Three options will be presented:
   - **转换为Qlib格式** - Opens conversion tool
   - **手动修改指引** - Shows manual conversion guide
   - **取消** - Discard and try another file

### In Strategy Conversion Module
1. Navigate to **回测中心 → 策略转换**
2. Upload or paste the content of an example file
3. Platform should be **auto-detected**
4. Click **开始转换**
5. Wait 2 seconds (mock processing)
6. See Qlib-formatted output in right pane
7. Click **应用到快速回测** to use in backtest

## Expected Behavior

### Platform Detection Patterns

**JoinQuant:**
- `initialize(context)` function
- `handle_data` function
- `set_universe`, `order_target_percent` calls

**RiceQuant:**
- `init(context)` function
- `scheduler.run_` calls
- `bar_dict` parameter usage

**Backtrader:**
- `bt.Strategy` class inheritance
- `bt.indicators` usage
- `self.position` attribute

## Validation Results

### ✅ Qlib Format (examples/qlib_topk_dropout_example.py)
```
Status: Success
Format: Qlib
Action: Auto-load into backtest form
```

### ⚠️ Non-Qlib Format (all files in this directory)
```
Status: Warning
Format: [Detected Platform]
Action: Show conversion options
```

### ❌ Invalid Python (create a file with syntax errors to test)
```
Status: Error
Format: Invalid
Action: Show error message with line number
```

## Integration with Backend

When backend APIs are implemented, these files will test:
- Real platform detection algorithms (AST-based)
- Actual LLM conversion (GPT-4/Claude-3)
- Strategy validation with Python sandbox
- Conversion quality scoring

## Adding More Examples

To add a new test case:
1. Create `[platform]_example.py` in this directory
2. Add platform-specific code patterns
3. Update this README with detection patterns
4. Test in both Quick Backtest and Conversion modules

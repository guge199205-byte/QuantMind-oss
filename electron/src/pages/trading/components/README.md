# Trading Components

## 组件说明

- `PositionOverview.tsx`：实盘交易页和策略状态页共享的持仓概览组件，统一渲染持仓分布饼图与持仓明细表，数据源来自标准化后的 `holdings + summary`。
- `LiveTradeConfigForm.tsx`：实盘交易执行参数表单。
- `LiveTradeConfigWizard.tsx`：实盘执行参数向导。
- `TopBar.tsx`：交易页顶部工具栏。

## 设计约束

- 持仓相关展示优先复用 `PositionOverview.tsx`，避免不同页面各自维护一套图表和表格口径。
- 页面级组件负责数据拉取、权限控制和外层布局，组件级模块只负责展示与交互。

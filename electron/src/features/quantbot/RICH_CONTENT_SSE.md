# OpenClaw 富文本渲染与实时通信 (SSE & Polling)

## 功能概述

OpenClaw现已支持：
1. **富文本内容渲染** - 财报卡片、股票行情、图表等
2. **实时通信** - 基于 SSE (Server-Sent Events) 的流式对话和基于轮询的任务状态更新

---

## 富文本组件

### 1. FinancialCard - 财报卡片

展示公司财务数据的卡片组件。

```tsx
import { FinancialCard } from '@/features/openclaw/components/RichContent';

<FinancialCard
  title="财务数据分析"
  subtitle="2024年第二季度"
  companyName="贵州茅台"
  tsCode="600519.SH"
  period="2024Q2"
  metrics={[
    {
      label: '营业收入',
      value: 125000000000,
      unit: '元',
      change: 15.8,
      changeType: 'increase',
      highlight: true
    },
    // ... 更多指标
  ]}
/>
```

**特性：**
- ✅ 支持多个财务指标
- ✅ 显示变化率和趋势
- ✅ 高亮显示重要指标
- ✅ 自动格式化数字

### 2. StockQuoteCard - 股票行情卡片

显示股票实时行情信息。

```tsx
import { StockQuoteCard } from '@/features/openclaw/components/RichContent';

<StockQuoteCard
  symbol="600519.SH"
  name="贵州茅台"
  price={1580.50}
  change={25.80}
  changePercent={1.66}
  volume={1250000}
  turnover={19750000000}
  high={1595.20}
  low={1565.30}
  open={1570.00}
  close={1554.70}
  timestamp="2024-12-25 15:00:00"
/>
```

**特性：**
- ✅ 实时价格显示
- ✅ 红涨绿跌配色
- ✅ 成交量/额展示

### 3. TrendChart - 趋势图表

基于 Recharts 的趋势图表组件。

```tsx
import { TrendChart } from '@/features/openclaw/components/RichContent';

<TrendChart
  title="营收与净利润趋势"
  subtitle="最近6个季度数据"
  data={[
    { name: '2023Q1', revenue: 28500, netProfit: 4200 },
    { name: '2023Q2', revenue: 31200, netProfit: 4800 },
    // ...
  ]}
  series={[
    { key: 'revenue', name: '营业收入', color: '#3b82f6' },
    { key: 'netProfit', name: '净利润', color: '#10b981' },
  ]}
  type="line" // 或 'area', 'bar'
  height={300}
/>
```

### 4. KLineChart - K线图

基于 ECharts 的K线图组件。

```tsx
import { KLineChart } from '@/features/openclaw/components/RichContent';

<KLineChart
  title="贵州茅台 K线图"
  subtitle="600519.SH - 日K"
  data={[
    { date: '2024-01-01', open: 100, close: 105, low: 98, high: 107, volume: 12500000 },
    // ...
  ]}
  height={500}
/>
```

### 5. RichContentRenderer - 统一渲染器

根据消息类型自动渲染对应组件。

```tsx
import { RichContentRenderer } from '@/features/openclaw/components/RichContent';

<RichContentRenderer
  content={{
    type: 'financial_card',
    data: {
      title: '财务分析',
      metrics: [...]
    }
  }}
/>
```

---

## 实时通信架构

OpenClaw 使用混合架构实现实时交互：

1.  **流式对话 (SSE)**: 使用 `POST /chat/stream` 接口，通过 Server-Sent Events 技术实现 AI 回复的打字机效果。
2.  **任务状态 (Polling)**: 使用 `useTaskPolling` Hook 定期查询后台任务状态。

### 1. 流式对话 (Chat Stream)

前端通过 `agentApi.chatStream` 方法发起请求并处理流式响应。

```typescript
await agentApi.chatStream(message, {
  onChunk: (chunk) => {
    // 更新消息内容
    dispatch(updateMessageContent(chunk));
  },
  onDone: (payload) => {
    // 处理完成信号（如生成的任务列表）
    if (payload.tasks) {
      dispatch(addTasks(payload.tasks));
    }
  }
});
```

**响应格式 (SSE Data)**:

```
data: {"type": "meta", "session_id": "...", ...}

data: {"answer": "正在为您分析..."}

data: {"answer": "茅台的财务状况..."}

data: {"done": true, "tasks": [...]}
```

### 2. 任务轮询 (Task Polling)

使用 `useTaskPolling` Hook 自动管理任务状态同步。

```tsx
import { useTaskPolling } from '@/features/openclaw/hooks/useTaskPolling';

function OpenClawPage() {
  // 每 3 秒轮询一次活跃任务
  const { fetchTasks } = useTaskPolling(true, 3000);
  
  // ...
}
```

**支持的状态更新：**
- `pending` -> `running`
- `running` -> `completed` / `failed`

---

## 在消息中使用富文本

### 添加富文本到消息

```typescript
import { addMessage } from '@/features/openclaw/store/chatSlice';

dispatch(addMessage({
  id: 'msg-001',
  type: 'ai',
  content: '这是贵州茅台的财务分析：',
  timestamp: new Date(),
  richContent: {
    type: 'financial_card',
    data: {
      title: '财务数据分析',
      companyName: '贵州茅台',
      tsCode: '600519.SH',
      metrics: [
        { label: '营业收入', value: 125000000000, unit: '元' },
        // ...
      ]
    }
  }
}));
```

---

## 技术栈

- **富文本渲染**
  - React + TypeScript
  - Recharts (折线图、柱状图等)
  - ECharts (K线图)
  - Framer Motion (动画)
  - Tailwind CSS (样式)

- **通信**
  - Axios + Fetch API (SSE)
  - Redux Toolkit (状态管理)
  - React Hooks (Polling)

---

## 故障排查

### 消息不显示打字机效果

1.  检查网络面板 `POST /chat/stream` 请求是否处于 Pending 状态并持续接收数据。
2.  确认后端是否正确启用 SSE 响应。

### 任务状态不更新

1.  检查 `useTaskPolling` 是否启用 (enabled=true)。
2.  检查 `/api/openclaw/tasks/active` 接口是否返回数据。
3.  确认后端 Redis 连接正常。

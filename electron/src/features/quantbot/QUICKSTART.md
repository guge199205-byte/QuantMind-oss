# OpenClaw 富文本 & WebSocket - 快速启动指南

## 🚀 快速开始

### 1. 安装依赖（已完成）

所需依赖已经安装：
```bash
✅ socket.io-client
✅ recharts
✅ echarts
✅ echarts-for-react
```

### 2. 查看示例

运行开发服务器并访问示例页面：

```bash
cd electron
npm run dev
```

然后在代码中导入示例组件查看效果。

### 3. 基本使用

#### 方式一：在消息中使用富文本

```typescript
import { useDispatch } from 'react-redux';
import { addMessage } from '@/features/openclaw/store/chatSlice';

function MyComponent() {
  const dispatch = useDispatch();

  const sendFinancialData = () => {
    dispatch(addMessage({
      id: `msg-${Date.now()}`,
      type: 'ai',
      content: '这是茅台的财务分析：',
      timestamp: new Date(),
      richContent: {
        type: 'financial_card',
        data: {
          title: '财务数据分析',
          companyName: '贵州茅台',
          tsCode: '600519.SH',
          metrics: [
            { label: '营业收入', value: 125000000000, unit: '元', highlight: true }
          ]
        }
      }
    }));
  };
}
```

#### 方式二：直接使用组件

```typescript
import { FinancialCard } from '@/features/openclaw/components/RichContent';

function MyComponent() {
  return (
    <FinancialCard
      title="财务分析"
      companyName="贵州茅台"
      tsCode="600519.SH"
      metrics={[
        { label: '营业收入', value: 125000000000, unit: '元' }
      ]}
    />
  );
}
```

#### 方式三：使用WebSocket

```typescript
import { useWebSocket } from '@/features/openclaw/hooks/useWebSocket';

function MyComponent() {
  const sessionId = 'my-session-id';
  const { isConnected, subscribeToTask, subscribeToPrice } = useWebSocket(sessionId);

  useEffect(() => {
    if (isConnected) {
      subscribeToTask('task-123');
      subscribeToPrice('600519.SH');
    }
  }, [isConnected]);

  return <div>WebSocket: {isConnected ? '已连接' : '未连接'}</div>;
}
```

## 📊 组件速查

### FinancialCard - 财报卡片
```typescript
<FinancialCard
  title="财务数据"
  subtitle="2024Q2"
  companyName="公司名"
  tsCode="股票代码"
  period="期间"
  metrics={[
    {
      label: '指标名',
      value: 123456,
      unit: '元',
      change: 15.5,
      changeType: 'increase',
      highlight: true
    }
  ]}
/>
```

### StockQuoteCard - 股票行情
```typescript
<StockQuoteCard
  symbol="600519.SH"
  name="贵州茅台"
  price={1580.50}
  change={25.80}
  changePercent={1.66}
  volume={1250000}
  high={1595.20}
  low={1565.30}
  open={1570.00}
  close={1554.70}
/>
```

### TrendChart - 趋势图
```typescript
<TrendChart
  title="营收趋势"
  data={[
    { name: '2024Q1', revenue: 28500, netProfit: 4200 },
    { name: '2024Q2', revenue: 31200, netProfit: 4800 },
  ]}
  series={[
    { key: 'revenue', name: '营收', color: '#3b82f6' },
    { key: 'netProfit', name: '净利润', color: '#10b981' }
  ]}
  type="line" // 或 'area', 'bar'
/>
```

### KLineChart - K线图
```typescript
<KLineChart
  title="股票K线"
  data={[
    { date: '2024-01-01', open: 100, close: 105, low: 98, high: 107, volume: 12500000 }
  ]}
  height={500}
/>
```

## 🔧 WebSocket事件

### 监听事件

WebSocket Hook 自动处理以下事件：

- `task_status` → 自动更新任务状态
- `task_complete` → 自动标记任务完成并添加消息
- `price_update` → 价格实时更新
- `chat_response` → 添加AI回复消息
- `error` → 显示错误消息

### 发送订阅

```typescript
const { subscribeToTask, subscribeToPrice } = useWebSocket(sessionId);

// 订阅任务
subscribeToTask('task-id');

// 订阅价格
subscribeToPrice('600519.SH');
```

## 📁 重要文件位置

### 组件
```
src/features/openclaw/components/RichContent/
├── FinancialCard.tsx       # 财报卡片
├── StockQuoteCard.tsx      # 行情卡片
├── TrendChart.tsx          # 趋势图
├── KLineChart.tsx          # K线图
└── RichContentRenderer.tsx # 统一渲染器
```

### Hooks
```
src/features/openclaw/hooks/
└── useWebSocket.ts         # WebSocket Hook
```

### 示例
```
src/features/openclaw/examples/
└── RichContentExample.tsx  # 完整示例
```

## 💡 常见用例

### 1. 展示财报分析结果

```typescript
dispatch(addMessage({
  id: `msg-${Date.now()}`,
  type: 'ai',
  content: '分析完成，以下是主要财务指标：',
  timestamp: new Date(),
  richContent: {
    type: 'financial_card',
    data: {
      title: '财务分析',
      companyName: '公司名',
      metrics: [
        { label: '营收', value: 1000000, unit: '元' },
        { label: 'ROE', value: 15.5, unit: '%' }
      ]
    }
  }
}));
```

### 2. 显示实时行情

```typescript
// WebSocket会自动接收price_update事件并更新
// 或手动添加：
dispatch(addMessage({
  id: `msg-${Date.now()}`,
  type: 'ai',
  content: '当前行情：',
  timestamp: new Date(),
  richContent: {
    type: 'stock_quote',
    data: {
      symbol: '600519.SH',
      name: '贵州茅台',
      price: 1580.50,
      change: 25.80,
      changePercent: 1.66
    }
  }
}));
```

### 3. 绘制趋势图

```typescript
dispatch(addMessage({
  id: `msg-${Date.now()}`,
  type: 'ai',
  content: '最近6个季度营收趋势：',
  timestamp: new Date(),
  richContent: {
    type: 'trend_chart',
    data: {
      title: '营收趋势',
      data: [
        { name: 'Q1', revenue: 28500 },
        { name: 'Q2', revenue: 31200 }
      ],
      series: [
        { key: 'revenue', name: '营收', color: '#3b82f6' }
      ],
      type: 'line'
    }
  }
}));
```

### 4. 展示K线图

```typescript
dispatch(addMessage({
  id: `msg-${Date.now()}`,
  type: 'ai',
  content: '最近5日K线：',
  timestamp: new Date(),
  richContent: {
    type: 'kline_chart',
    data: {
      title: 'K线图',
      data: [
        { date: '2024-01-01', open: 100, close: 105, low: 98, high: 107, volume: 12500000 }
      ],
      height: 400
    }
  }
}));
```

## ⚡ 性能建议

1. **图表数据量**：建议单个图表数据点不超过1000个
2. **WebSocket消息**：避免频繁发送大量消息
3. **动画优化**：在低性能设备上可考虑关闭动画
4. **内存管理**：定期清理历史消息

## 🐛 故障排查

### WebSocket连接失败
```
1. 检查后端是否运行（默认端口8002）
2. 查看浏览器控制台错误
3. 确认sessionId正确
```

### 图表不显示
```
1. 检查数据格式是否正确
2. 确认echarts/recharts已安装
3. 查看控制台错误信息
```

### 富文本渲染异常
```
1. 验证richContent.type是否匹配
2. 检查data字段是否完整
3. 确保组件正确导入
```

## 📚 更多文档

- [完整API文档](./RICH_CONTENT_WEBSOCKET.md)
- [实施总结](./IMPLEMENTATION_SUMMARY.md)
- [示例代码](./examples/RichContentExample.tsx)

## 🎯 下一步

1. 查看示例页面了解所有组件
2. 阅读完整API文档
3. 在项目中集成使用
4. 根据需求自定义样式和功能

---

**需要帮助？** 查看文档或在团队中提问！

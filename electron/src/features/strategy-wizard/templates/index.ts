export type StrategyTemplate = {
  id: string;
  name: string;
  buy: Array<{ name: string; params?: Record<string, any> }>;
  sell: Array<{ name: string; params?: Record<string, any> }>;
};

export const TEMPLATES: StrategyTemplate[] = [
  {
    id: 'ma_cross',
    name: '均线交叉',
    buy: [{ name: 'MA_cross', params: { fast: 20, slow: 60 } }],
    sell: [{ name: 'indicator_reverse', params: { name: 'MA_cross' } }],
  },
  {
    id: 'macd_golden',
    name: 'MACD金叉',
    buy: [{ name: 'MACD_golden', params: { signal: 9 } }],
    sell: [{ name: 'stop_loss', params: { pct: 5 } }, { name: 'take_profit', params: { pct: 15 } }],
  },
  {
    id: 'rsi_rebound',
    name: 'RSI超卖反弹',
    buy: [{ name: 'RSI_rebound', params: { period: 14, low: 30 } }],
    sell: [{ name: 'indicator_reverse', params: { name: 'RSI_rebound' } }],
  },
];

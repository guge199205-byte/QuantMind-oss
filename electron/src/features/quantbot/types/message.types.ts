/**
 * 消息相关类型定义
 */

export type MessageType = 'user' | 'ai' | 'system';
export type MessageStatus = 'sending' | 'sent' | 'error';

export interface AgentAction {
  type: 'fetch_financials' | 'fetch_market' | 'place_order' | 'subscribe_quotes' | 'smart_screening';
  status: 'pending' | 'running' | 'success' | 'failed';
  description: string;
  result?: any;
}

export interface ToolCallResult {
  tool: string;
  ok: boolean;
  detail: Record<string, any>;
  error?: string;
}

export interface RichContent {
  type: 'financial_card' | 'stock_quote' | 'trend_chart' | 'kline_chart' | 'text' | 'code' | 'table';
  data: any;
}

export interface MessageAttachment {
  file_id?: string;
  original_name: string;
  file_name?: string;
  file_size?: number;
  content_type?: string;
  file_path?: string;
  uploaded_at?: string;
}

export interface Message {
  id: string;
  type: MessageType;
  content: string;
  /** ISO 8601 字符串，使用 new Date().toISOString()，不使用 Date 对象（Redux 序列化要求） */
  timestamp: string;
  status?: MessageStatus;

  // AI消息专属字段
  actions?: AgentAction[];
  results?: ToolCallResult[];

  // 富文本内容
  richContent?: RichContent;
  attachments?: MessageAttachment[];
}

// 财报卡片数据
export interface FinancialReportData {
  company: string;
  tsCode: string;
  metrics: {
    revenue?: number;
    netProfit?: number;
    roe?: number;
    grossProfitMargin?: number;
    debtRatio?: number;
    totalAssets?: number;
    totalLiab?: number;
    cashFlow?: number;
  };
  periods?: Array<{
    endDate: string;
    revenue?: number;
    netProfit?: number;
  }>;
  summary: string;
}

// 交易订单数据
export interface TradeOrderData {
  symbol: string;
  symbolName: string;
  side: 'buy' | 'sell';
  quantity: number;
  targetPrice: number;
  currentPrice?: number;
  status: 'monitoring' | 'executed' | 'failed' | 'dry_run';
  orderId?: string;
  message?: string;
}

// 行情数据
export interface QuoteData {
  symbol: string;
  symbolName: string;
  lastClose?: number;
  pctChg?: number;
  high?: number;
  low?: number;
  open?: number;
  preClose?: number;
}

// 选股结果数据
export interface StockScreeningData {
  stocks: Array<{
    tsCode: string;
    name: string;
    metrics?: Record<string, any>;
  }>;
  conditions: string[];
  total: number;
}

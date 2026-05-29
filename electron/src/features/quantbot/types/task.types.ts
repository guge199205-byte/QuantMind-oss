/**
 * 任务相关类型定义
 */

export type TaskType =
  | 'financial_report'
  | 'stock_query'
  | 'stock_selection'
  | 'strategy_advice'
  | 'strategy_analysis'
  | 'trade_execution'
  | 'software_info'
  | 'general_chat'
  | 'deep_analysis';
export type TaskStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';

export interface MonitorData {
  symbol: string;
  symbolName: string;
  currentPrice: number;
  targetPrice: number;
  condition: string;
  checkCount: number;
  side: 'buy' | 'sell';
  quantity: number;
}

export interface TaskAction {
  label: string;
  onClick: () => void;
  variant?: 'primary' | 'danger' | 'default';
}

export interface ActiveTask {
  id: string;
  type: TaskType;
  title: string;
  description: string;
  status: TaskStatus;
  progress?: number;
  /** ISO 8601 字符串 */
  createdAt: string;
  estimatedTime?: number; // 秒

  // 监控任务专属
  monitorData?: MonitorData;

  // 操作按钮
  actions?: TaskAction[];
}

export interface HistoryTask {
  id: string;
  type: TaskType;
  title: string;
  status: 'completed' | 'failed';
  /** ISO 8601 字符串 */
  completedAt: string;
  result?: string;

  // 快速操作
  canRetry?: boolean;
  canView?: boolean;
}

export interface TaskStatistics {
  total: number;
  active: number;
  completed: number;
  failed: number;
  successRate: number;
}

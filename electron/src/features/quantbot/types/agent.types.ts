/**
 * Agent相关类型定义
 */

export interface GuideSection {
  category: string;
  icon: string;
  examples: string[];
  isExpanded: boolean;
}

export interface QuickAction {
  label: string;
  prompt: string;
  icon: string;
  color: string;
}

export interface ChatRequest {
  message: string;
  source?: string;
  confirm?: boolean;
  dry_run?: boolean;
}

export interface ChatResponse {
  success: boolean;
  actions: string[];
  results: Array<{
    tool: string;
    ok: boolean;
    detail: Record<string, any>;
    error?: string;
  }>;
  reply: string;
  generated_at: string;
}

export interface AnalyzeRequest {
  company: string;
  source?: string;
  period?: string;
  recent_periods?: number;
}

export interface AnalyzeResponse {
  success: boolean;
  source_used: string;
  ts_code?: string;
  company_name?: string;
  metrics: Record<string, any>;
  periods: Array<Record<string, any>>;
  summary: string;
  generated_at: string;
}

export interface WebSocketMessage {
  type: 'task_status' | 'price_update' | 'task_complete' | 'error';
  taskId?: string;
  status?: string;
  price?: number;
  result?: any;
  message?: string;
}

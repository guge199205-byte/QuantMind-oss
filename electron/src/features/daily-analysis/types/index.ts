// Daily Stock Analysis types

export interface TaskInfo {
  task_id: string;
  trace_id?: string;
  stock_code: string;
  stock_name?: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  progress: number;
  message?: string;
  report_type?: string;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  error?: string;
  original_query?: string;
  selection_source?: string;
}

export interface TaskListResponse {
  total: number;
  pending: number;
  processing: number;
  tasks: TaskInfo[];
}

export interface TaskAccepted {
  task_id: string;
  trace_id?: string;
  status: string;
  message: string;
}

export interface AnalysisReport {
  meta: {
    id?: number;
    query_id: string;
    stock_code: string;
    stock_name: string;
    report_type?: string;
    report_language?: string;
    created_at?: string;
    model_used?: string;
    current_price?: number;
    change_pct?: number;
  };
  summary: {
    analysis_summary?: string;
    operation_advice?: string;
    trend_prediction?: string;
    sentiment_score?: number;
    sentiment_label?: string;
  };
  strategy?: {
    ideal_buy?: string;
    secondary_buy?: string;
    stop_loss?: string;
    take_profit?: string;
  };
  details?: {
    news_content?: string;
    raw_result?: any;
    context_snapshot?: any;
    financial_report?: any;
    dividend_metrics?: any;
    belong_boards?: any;
    sector_rankings?: any;
  };
}

export interface AnalysisResultResponse {
  query_id: string;
  trace_id?: string;
  stock_code: string;
  stock_name?: string;
  report?: AnalysisReport;
  diagnostic_summary?: any;
  created_at: string;
}

export interface TaskStatus {
  task_id: string;
  trace_id?: string;
  status: string;
  progress: number;
  result?: AnalysisResultResponse;
  market_review_report?: string;
  error?: string;
  stock_name?: string;
  original_query?: string;
  selection_source?: string;
  skills?: string[];
}

export interface AnalyzeRequest {
  stock_code?: string;
  stock_codes?: string[];
  stock_name?: string;
  original_query?: string;
  selection_source?: string;
  report_type?: string;
  force_refresh?: boolean;
  async_mode?: boolean;
  notify?: boolean;
  skills?: string[];
}

export interface StockSearchResult {
  code: string;
  name: string;
  market?: string;
}

export interface MarketReviewRequest {
  send_notification?: boolean;
}

export interface MarketReviewAccepted {
  status: string;
  message: string;
  send_notification?: boolean;
  task_id?: string;
  trace_id?: string;
}

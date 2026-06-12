/**
 * Strategy Lab — type definitions matching backend RunResult schema
 * (see backend/services/engine/strategy_lab/runner/result_collector.py).
 */

export interface StrategyLabMetrics {
  cum_return: number;
  annual_return: number;
  sharpe: number;
  max_drawdown: number;
  win_rate: number;
  n_trades: number;
  avg_position: number;
}

export interface StrategyLabEquityPoint {
  date: string;
  value: number;
  benchmark: number | null;
}

export interface StrategyLabTradeRecord {
  date: string;
  symbol: string;
  direction: 'BUY' | 'SELL';
  price: number;
  qty: number;
  reason: string;
  detail: Record<string, unknown>;
  pnl: number | null;
}

export interface StrategyLabPositionSnapshot {
  date: string;
  symbol: string;
  qty: number;
  cost: number;
  market_value: number;
  pnl_pct: number;
}

export interface StrategyLabLogEntry {
  level: 'debug' | 'info' | 'warning' | 'error';
  ts: string | null;
  msg: string;
}

export interface StrategyLabRunResult {
  run_id: string;
  status: 'queued' | 'running' | 'success' | 'failed' | 'cancelled';
  metrics: StrategyLabMetrics;
  equity: StrategyLabEquityPoint[];
  trades: StrategyLabTradeRecord[];
  positions: StrategyLabPositionSnapshot[];
  overlays: {
    lines?: Array<{ name: string; symbol: string | null; ts: string | null; value: number }>;
    markers?: Array<{ symbol: string; type: string; text: string; price: number | null; ts: string | null }>;
  };
  logs: StrategyLabLogEntry[];
  warnings: string[];
  error: string | null;
  error_traceback: string | null;
  config: Record<string, unknown>;
  script_sha: string;
  data_snapshot_at: string | null;
  elapsed_sec: number;
  started_at: number;
  finished_at: number;
}

export type StrategyLabPhase =
  | 'queued'
  | 'boot'
  | 'ast_check'
  | 'setup'
  | 'load_data'
  | 'backtest'
  | 'aggregate'
  | 'done';

export interface StrategyLabProgressEvent {
  run_id: string;
  phase: StrategyLabPhase;
  pct: number;
  message: string;
  detail: Record<string, unknown>;
  ts: number;
}

export interface StrategyLabRunRequest {
  code: string;
  params?: Record<string, unknown>;
  options?: Record<string, unknown>;
  qlib_data_path?: string | null;
  timeout_sec?: number | null;
}

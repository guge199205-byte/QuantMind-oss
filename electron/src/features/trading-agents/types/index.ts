/** TradingAgents type definitions */

export interface PipelineStage {
  id: string;
  name: string;
  icon: string;
  report_key: string;
}

export interface AnalysisProgress {
  ticker: string;
  trade_date: string;
  is_running: boolean;
  is_complete: boolean;
  error?: string;
  current_stage: string;
  completed_stages: string[];
  stage_reports: Record<string, string>;
  signal?: string;
  stats: {
    llm_calls: number;
    tool_calls: number;
    tokens_in: number;
    tokens_out: number;
  };
  elapsed: number;
}

export interface AnalysisReport {
  ticker: string;
  trade_date: string;
  signal: string;
  final_state: Record<string, any>;
  stage_reports: Record<string, string>;
  stats: {
    llm_calls: number;
    tool_calls: number;
    tokens_in: number;
    tokens_out: number;
  };
  elapsed: number;
}

export interface AnalysisHistoryItem {
  analysis_id: string;
  ticker: string;
  trade_date: string;
  signal: string;
  elapsed: number;
  source: 'memory' | 'disk';
}

export interface LLMProvider {
  key: string;
  quick_models: { label: string; value: string }[];
  deep_models: { label: string; value: string }[];
}

export const PIPELINE_STAGES: PipelineStage[] = [
  { id: 'market', name: '技术分析', icon: '📊', report_key: 'market_report' },
  { id: 'social', name: '情绪分析', icon: '💬', report_key: 'sentiment_report' },
  { id: 'news', name: '新闻舆情', icon: '📰', report_key: 'news_report' },
  { id: 'fundamentals', name: '基本面', icon: '📋', report_key: 'fundamentals_report' },
  { id: 'policy', name: '政策分析', icon: '🏛️', report_key: 'policy_report' },
  { id: 'hot_money', name: '游资追踪', icon: '🔥', report_key: 'hot_money_report' },
  { id: 'lockup', name: '解禁监控', icon: '🔒', report_key: 'lockup_report' },
  { id: 'quality_gate', name: '质量门控', icon: '✅', report_key: 'data_quality_summary' },
  { id: 'debate', name: '多空辩论', icon: '⚔️', report_key: 'investment_plan' },
  { id: 'trader', name: '交易决策', icon: '💹', report_key: 'trader_investment_plan' },
  { id: 'risk', name: '风控评估', icon: '🛡️', report_key: 'risk_debate_state' },
  { id: 'pm', name: '最终决策', icon: '👔', report_key: 'final_trade_decision' },
];

export const ANALYST_SECTIONS = [
  { key: 'market_report', label: '📊 技术分析' },
  { key: 'sentiment_report', label: '💬 市场情绪' },
  { key: 'news_report', label: '📰 新闻舆情' },
  { key: 'fundamentals_report', label: '📋 基本面' },
  { key: 'policy_report', label: '🏛️ 政策分析' },
  { key: 'hot_money_report', label: '🔥 游资追踪' },
  { key: 'lockup_report', label: '🔒 解禁/减持' },
];

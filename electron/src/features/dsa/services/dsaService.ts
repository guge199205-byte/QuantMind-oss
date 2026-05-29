import { authService } from '../../auth/services/authService';

const BASE = '/api/v1/admin/dsa/api/v1';

async function fetchJSON<T>(path: string, init?: RequestInit): Promise<T> {
  const url = BASE + path;
  const token = await authService.getAccessToken();
  const resp = await fetch(url, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
      ...(init?.headers || {}),
    },
  });
  if (!resp.ok) {
    const body = await resp.text().catch(() => '');
    throw new Error(`DSA API ${resp.status}: ${body}`);
  }
  return resp.json();
}

async function postJSON<T>(path: string, body: unknown): Promise<T> {
  return fetchJSON<T>(path, { method: 'POST', body: JSON.stringify(body) });
}

export const dsaService = {
  // Auth
  getAuthStatus: () => fetchJSON<any>('/auth/status'),
  login: (password: string) => postJSON<any>('/auth/login', { password }),

  // Analysis
  analyze: (params: {
    stock_codes: string[];
    analysis_date?: string;
    llm_provider?: string;
    llm_model?: string;
    enable_news?: boolean;
    enable_financial_report?: boolean;
    output_format?: string;
  }) => postJSON<any>('/analysis/analyze', params),

  marketReview: (params: {
    analysis_date?: string;
    stock_pool?: string[];
    llm_provider?: string;
    llm_model?: string;
  }) => postJSON<any>('/analysis/market-review', params),

  getTasks: (status?: string, limit = 20) =>
    fetchJSON<any>(`/analysis/tasks?limit=${limit}${status ? `&status=${status}` : ''}`),

  getTaskStatus: (taskId: string) => fetchJSON<any>(`/analysis/status/${taskId}`),

  // History
  getHistory: (page = 1, pageSize = 20) =>
    fetchJSON<any>(`/history?page=${page}&page_size=${pageSize}`),

  getHistoryDetail: (recordId: string) => fetchJSON<any>(`/history/${recordId}`),

  getHistoryDiagnostics: (recordId: string) =>
    fetchJSON<any>(`/history/${recordId}/diagnostics`),

  getHistoryNews: (recordId: string) => fetchJSON<any>(`/history/${recordId}/news`),

  getHistoryMarkdown: (recordId: string) =>
    fetchJSON<{ markdown: string }>(`/history/${recordId}/markdown`),

  deleteHistory: (recordId: string) =>
    fetchJSON<any>(`/history/${recordId}`, { method: 'DELETE' }),

  // Stocks
  getStockQuote: (code: string) => fetchJSON<any>(`/stocks/${code}/quote`),
  getStockHistory: (code: string) => fetchJSON<any>(`/stocks/${code}/history`),

  // Agent / Chat
  getAgentModels: () => fetchJSON<any>('/agent/models'),
  getAgentSkills: () => fetchJSON<any>('/agent/skills'),
  getAgentStrategies: () => fetchJSON<any>('/agent/strategies'),
  getChatSessions: () => fetchJSON<any>('/agent/chat/sessions'),
  deleteChatSession: (sessionId: string) =>
    fetchJSON<any>(`/agent/chat/sessions/${sessionId}`, { method: 'DELETE' }),
  sendChat: (params: {
    message: string;
    session_id?: string;
    model?: string;
    strategy?: string;
    stock_codes?: string[];
  }) => postJSON<any>('/agent/chat/send', params),

  // System config
  getSystemConfig: () => fetchJSON<any>('/system/config'),
  getSetupStatus: () => fetchJSON<any>('/system/config/setup/status'),

  // Backtest
  runBacktest: (params: any) => postJSON<any>('/backtest/run', params),
  getBacktestResults: () => fetchJSON<any>('/backtest/results'),

  // Portfolio
  getPortfolioAccounts: () => fetchJSON<any>('/portfolio/accounts'),
  getPortfolioSnapshot: () => fetchJSON<any>('/portfolio/snapshot'),

  // Alerts
  getAlertRules: () => fetchJSON<any>('/alerts/rules'),
  getAlertTriggers: () => fetchJSON<any>('/alerts/triggers'),
  getAlertNotifications: () => fetchJSON<any>('/alerts/notifications'),
};

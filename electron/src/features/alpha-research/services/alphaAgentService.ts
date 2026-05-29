import { apiClient } from '../../../services/aiStrategyClients';

const ALPHA_AGENT_BASE = '/alpha-agent';

export interface EvolutionTask {
  task_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress: string;
  error_message: string | null;
  result: Record<string, unknown> | null;
}

export interface AlphaFactor {
  id: string;
  factor_name: string;
  factor_code: string;
  factor_formulation: string;
  category: string;
  status: string;
  ic_value: number | null;
  sharpe_ratio: number | null;
  annual_return: number | null;
  created_at: string;
  task_id: string;
  user_id: string;
  metadata: Record<string, unknown>;
}

export interface EvolutionStats {
  total: number;
  completed: number;
  pending: number;
  backtesting: number;
  failed: number;
  avg_ic: number | null;
  avg_sharpe: number | null;
  best_ic: number | null;
  best_sharpe: number | null;
}

export interface EvolutionRequest {
  user_id: string;
  market?: string;
  loop_n?: number;
  direction?: string;
}

export interface MarketInfo {
  market_id: string;
  market_name: string;
  description: string;
  data_ready: boolean;
}

export const alphaAgentService = {
  startEvolution: async (req: EvolutionRequest): Promise<{ task_id: string; market: string; market_name: string }> => {
    const params = new URLSearchParams({ user_id: req.user_id });
    if (req.market) params.set('market', req.market);
    if (req.loop_n) params.set('loop_n', String(req.loop_n));
    if (req.direction) params.set('direction', req.direction);
    const res = await apiClient.post(`${ALPHA_AGENT_BASE}/evolve?${params}`);
    return res.data.data;
  },

  listMarkets: async (): Promise<MarketInfo[]> => {
    const res = await apiClient.get(`${ALPHA_AGENT_BASE}/markets`);
    return res.data.data.markets;
  },

  getTaskStatus: async (taskId: string): Promise<EvolutionTask> => {
    const res = await apiClient.get(`${ALPHA_AGENT_BASE}/tasks/${taskId}`);
    return res.data.data;
  },

  cancelTask: async (taskId: string): Promise<void> => {
    await apiClient.post(`${ALPHA_AGENT_BASE}/tasks/${taskId}/cancel`);
  },

  getTaskLog: async (taskId: string, tail = 200): Promise<{ task_id: string; log: string }> => {
    const res = await apiClient.get(`${ALPHA_AGENT_BASE}/tasks/${taskId}/log?tail=${tail}`);
    return res.data.data;
  },

  listTasks: async (userId?: string): Promise<EvolutionTask[]> => {
    const params = new URLSearchParams();
    if (userId) params.set('user_id', userId);
    const res = await apiClient.get(`${ALPHA_AGENT_BASE}/tasks?${params}`);
    return res.data.data.tasks;
  },

  listFactors: async (opts?: {
    userId?: string;
    status?: string;
    limit?: number;
  }): Promise<AlphaFactor[]> => {
    const params = new URLSearchParams();
    if (opts?.userId) params.set('user_id', opts.userId);
    if (opts?.status) params.set('status', opts.status);
    if (opts?.limit) params.set('limit', String(opts.limit));
    const res = await apiClient.get(`${ALPHA_AGENT_BASE}/factors?${params}`);
    return res.data.data.factors;
  },

  getFactor: async (factorId: string): Promise<AlphaFactor> => {
    const res = await apiClient.get(`${ALPHA_AGENT_BASE}/factors/${factorId}`);
    return res.data.data;
  },

  backtestFactor: async (
    factorId: string,
    startDate?: string,
    endDate?: string,
  ): Promise<{ factor_id: string; status: string }> => {
    const params = new URLSearchParams();
    if (startDate) params.set('start_date', startDate);
    if (endDate) params.set('end_date', endDate);
    const res = await apiClient.post(
      `${ALPHA_AGENT_BASE}/factors/${factorId}/backtest?${params}`,
    );
    return res.data.data;
  },

  getStats: async (): Promise<EvolutionStats> => {
    const res = await apiClient.get(`${ALPHA_AGENT_BASE}/stats`);
    return res.data.data;
  },

  promoteFactors: async (
    factorIds: string[],
    autoTrain = false,
  ): Promise<{
    success: boolean;
    promoted: Array<{
      factor_id: string;
      factor_name: string;
      feature_key: string;
      expression: string;
      non_null_values: number;
    }>;
    errors: Array<{ factor_id: string; factor_name: string; error: string }>;
  }> => {
    const res = await apiClient.post(`/admin/alpha-factors/promote`, {
      factor_ids: factorIds,
      auto_train: autoTrain,
    });
    return res.data;
  },

  listExtractableFactors: async (limit = 50): Promise<{
    data: Array<{
      factor_id: string;
      factor_name: string;
      extractable: boolean;
      qlib_expression: string | null;
      ic_value: number | null;
      sharpe_ratio: number | null;
      annual_return: number | null;
    }>;
  }> => {
    const res = await apiClient.get(`/admin/alpha-factors/extractable?limit=${limit}`);
    return res.data;
  },

  promoteByExpression: async (
    factors: Array<{ name: string; expression: string }>,
  ): Promise<{
    success: boolean;
    promoted: Array<{
      factor_name: string;
      feature_key: string;
      expression: string;
      non_null_values: number;
    }>;
    errors: Array<{ factor_name: string; error: string }>;
  }> => {
    const res = await apiClient.post(`/admin/alpha-factors/promote-by-expression`, {
      factors,
    });
    return res.data;
  },
};
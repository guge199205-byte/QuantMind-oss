/**
 * AlphaAgent 因子挖掘服务 — 调用后端 /api/v1/alpha-agent 与 /api/v1/quantbot
 *
 * 走原生 axios + 拦截器（避开 createAPIClient 改写 baseURL 的坑）。
 */

import axios from 'axios';
import { SERVICE_ENDPOINTS } from '../../../config/services';
import { authService } from '../../auth/services/authService';

const apiClient = axios.create({ timeout: 60000 });

apiClient.interceptors.request.use((config) => {
  config.baseURL = SERVICE_ENDPOINTS.USER_SERVICE;
  const token = authService.getAccessToken();
  if (token) {
    config.headers = config.headers || {};
    (config.headers as any).Authorization = `Bearer ${token}`;
  }
  return config;
});

export type FactorStatus = 'pending' | 'backtesting' | 'completed' | 'failed';
export type TaskStatus = 'pending' | 'running' | 'completed' | 'failed';

export interface RDAgentFactor {
  factor_id: string;
  factor_name: string;
  factor_code?: string;
  status: FactorStatus;
  ic_value?: number | null;
  sharpe_ratio?: number | null;
  annual_return?: number | null;
  max_drawdown?: number | null;
  user_id?: string | null;
  metadata?: Record<string, any> | null;
  metadata_json?: Record<string, any> | string | null;
  created_at?: string;
  updated_at?: string;
}

export interface RDAgentStats {
  total: number;
  completed: number;
  pending: number;
  backtesting: number;
  failed: number;
  avg_ic?: number | null;
  avg_sharpe?: number | null;
  best_ic?: number | null;
  best_sharpe?: number | null;
}

export interface QuantBotTask {
  task_id: string;
  status: TaskStatus;
  progress?: string | null;
  result?: any;
  error_message?: string | null;
  factor_ids?: string[] | null;
  created_at?: string;
  updated_at?: string;
  completed_at?: string | null;
  request_json?: any;
}

export interface ChatTriggerResponse {
  intent: string;
  task_id?: string;
  answer?: string;
}

function unwrap<T = any>(payload: any): T {
  // 后端 envelope: {code, data}; 部分接口直接返回数据
  if (payload && typeof payload === 'object' && 'data' in payload && 'code' in payload) {
    return payload.data as T;
  }
  return payload as T;
}

class RDAgentService {
  // -------------------- 因子 --------------------

  async listFactors(params: {
    user_id?: string;
    status?: FactorStatus;
    limit?: number;
  } = {}): Promise<RDAgentFactor[]> {
    const r = await apiClient.get('/alpha-agent/factors', { params });
    const body = unwrap<{ factors: RDAgentFactor[]; total: number }>(r.data);
    return body?.factors ?? [];
  }

  async getFactor(factorId: string): Promise<RDAgentFactor | null> {
    const r = await apiClient.get(`/alpha-agent/factors/${factorId}`);
    return unwrap<RDAgentFactor>(r.data) ?? null;
  }

  async backtestFactor(
    factorId: string,
    range?: { start_date?: string; end_date?: string },
  ): Promise<{ factor_id: string; status: string; message: string }> {
    const r = await apiClient.post(`/alpha-agent/factors/${factorId}/backtest`, null, {
      params: range,
    });
    return unwrap(r.data);
  }

  async getStats(): Promise<RDAgentStats> {
    const r = await apiClient.get('/alpha-agent/stats');
    return unwrap<RDAgentStats>(r.data) ?? ({} as RDAgentStats);
  }

  // -------------------- 任务 (QuantBot) --------------------

  async triggerEvolution(message: string): Promise<ChatTriggerResponse> {
    const r = await apiClient.post('/quantbot/chat', { message, history: [] });
    // 该接口直接返回 {intent, task_id, answer}
    return r.data as ChatTriggerResponse;
  }

  async listTasks(): Promise<QuantBotTask[]> {
    const r = await apiClient.get('/quantbot/tasks');
    const body = r.data;
    return (body?.tasks as QuantBotTask[]) ?? [];
  }

  async getTask(taskId: string): Promise<QuantBotTask | null> {
    const r = await apiClient.get(`/quantbot/task/${taskId}`);
    return (r.data as QuantBotTask) ?? null;
  }
}

export const rdAgentService = new RDAgentService();

// -------------------- 构造触发语 --------------------

export const FACTOR_TYPE_OPTIONS: Array<{ value: string; label: string; cn: string }> = [
  { value: 'value',      label: 'value',      cn: '价值' },
  { value: 'momentum',   label: 'momentum',   cn: '动量' },
  { value: 'volatility', label: 'volatility', cn: '波动' },
  { value: 'quality',    label: 'quality',    cn: '质量' },
  { value: 'growth',     label: 'growth',     cn: '成长' },
  { value: 'technical',  label: 'technical',  cn: '技术' },
  { value: '综合',       label: '综合',       cn: '综合' },
];

export function buildEvolutionMessage(opts: {
  factor_type: string;
  loop_n?: number;
  description?: string;
}): string {
  const ft = FACTOR_TYPE_OPTIONS.find(f => f.value === opts.factor_type)?.cn || opts.factor_type;
  const loop = opts.loop_n ?? 3;
  const extra = opts.description?.trim() ? `；附加要求：${opts.description.trim()}` : '';
  return `请帮我挖一批${ft}因子，执行 ${loop} 轮演化循环${extra}`;
}

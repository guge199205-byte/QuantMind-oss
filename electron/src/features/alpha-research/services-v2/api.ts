/**
 * QuantaAlpha frontend-v2 API bridge
 *
 * The original frontend-v2 expected its own dedicated FastAPI backend with
 * endpoints like /api/v1/mining/start, /api/v1/factors, WS /ws/mining/{id}.
 * In QuantMind we expose AlphaAgent under /api/v1/alpha-agent/* via the engine
 * service. This module preserves the original public surface (signatures,
 * return shapes) so the ported pages/components compile and run, but delegates
 * to the QuantMind alpha-agent router and normalizes the response shape.
 */

import { apiClient } from '../../../services/aiStrategyClients';
import type {
  ApiResponse,
  Factor,
  Task,
  TaskStatus,
  ExecutionPhase,
  RealtimeMetrics,
  WsMessage,
} from '../types-v2';

// ========================== Defaults ==========================

const DEFAULT_USER = 'alpha_researcher';

function makeOk<T>(data: T): ApiResponse<T> {
  return { success: true, data };
}

function emptyMetrics(): RealtimeMetrics {
  return {
    ic: 0,
    icir: 0,
    rankIc: 0,
    rankIcir: 0,
    annualReturn: 0,
    sharpeRatio: 0,
    maxDrawdown: 0,
    totalFactors: 0,
    highQualityFactors: 0,
    mediumQualityFactors: 0,
    lowQualityFactors: 0,
    top10Factors: [],
  };
}

function classifyQuality(ic: number | null | undefined): 'high' | 'medium' | 'low' {
  if (ic == null) return 'low';
  const v = Math.abs(ic);
  if (v >= 0.05) return 'high';
  if (v >= 0.02) return 'medium';
  return 'low';
}

function normalizeTaskStatus(raw: string | undefined): TaskStatus {
  switch (raw) {
    case 'completed':
      return 'completed';
    case 'failed':
    case 'cancelled':
      return 'failed';
    case 'running':
    case 'pending':
      return 'running';
    default:
      return 'idle';
  }
}

const PHASE_MAP: Record<string, ExecutionPhase> = {
  pending: 'parsing',
  starting: 'parsing',
  scenario: 'parsing',
  hypothesis: 'planning',
  experiment: 'planning',
  coder: 'evolving',
  runner: 'backtesting',
  summarizer: 'analyzing',
  completed: 'completed',
};

function normalizeAgentTask(raw: any, configHint?: any): Task {
  const status = normalizeTaskStatus(raw?.status);
  const backendPhase: string = typeof raw?.phase === 'string' ? raw.phase : '';
  let phase: ExecutionPhase = PHASE_MAP[backendPhase] || 'parsing';
  if (status === 'completed') phase = 'completed';
  else if (status === 'failed') phase = 'parsing';

  // Prefer backend's progress_pct; fall back to numeric progress; never fabricate 50%.
  let progressNum: number;
  if (typeof raw?.progress_pct === 'number') {
    progressNum = raw.progress_pct;
  } else if (typeof raw?.progress === 'number') {
    progressNum = raw.progress;
  } else if (status === 'completed') {
    progressNum = 100;
  } else if (status === 'failed') {
    progressNum = 0;
  } else if (status === 'running') {
    progressNum = 5;
  } else {
    progressNum = 0;
  }

  const currentRound = typeof raw?.current_loop === 'number' ? raw.current_loop : 0;
  const totalRounds = typeof raw?.loop_n === 'number' ? raw.loop_n : 0;

  return {
    taskId: raw?.task_id ?? raw?.taskId ?? '',
    status,
    config: configHint ?? { userInput: '' },
    progress: {
      phase,
      currentRound,
      totalRounds,
      progress: progressNum,
      message:
        typeof raw?.progress === 'string'
          ? raw.progress
          : raw?.error_message || (status === 'completed' ? '完成' : '运行中'),
      timestamp: raw?.updated_at ?? new Date().toISOString(),
    },
    metrics: emptyMetrics(),
    logs: [],
    createdAt: raw?.created_at ?? new Date().toISOString(),
    updatedAt: raw?.updated_at ?? new Date().toISOString(),
    timeline: raw?.timeline ?? undefined,
    tokenUsage: raw?.token_usage ?? undefined,
  };
}

function normalizeAgentFactor(raw: any): Factor {
  const ic = raw?.ic_value ?? null;
  return {
    factorId: raw?.id ?? raw?.factor_id ?? '',
    factorName: raw?.factor_name ?? 'unnamed',
    factorExpression: raw?.factor_formulation ?? raw?.factor_code ?? '',
    factorDescription: raw?.metadata?.description ?? raw?.category ?? '',
    quality: classifyQuality(ic),
    market: raw?.metadata?.market ?? raw?.market ?? undefined,
    ic: ic ?? 0,
    icir: 0,
    rankIc: 0,
    rankIcir: 0,
    round: raw?.metadata?.round ?? 0,
    direction: raw?.metadata?.direction ?? raw?.category ?? '',
    createdAt: raw?.created_at ?? '',
  };
}

// ========================== Mining API ==========================

export interface MiningStartParams {
  direction: string;
  market?: string;
  dataSource?: string;
  numDirections?: number;
  maxRounds?: number;
  maxLoops?: number;
  factorsPerHypothesis?: number;
  librarySuffix?: string;
  qualityGateEnabled?: boolean;
  parallelEnabled?: boolean;
}

export async function startMining(
  params: MiningStartParams,
): Promise<ApiResponse<{ taskId: string; task: Task }>> {
  const loopN = params.maxRounds ?? params.maxLoops ?? 3;
  const qs = new URLSearchParams({
    user_id: DEFAULT_USER,
    loop_n: String(loopN),
    direction: params.direction || '',
  });
  if (params.market) qs.set('market', params.market);
  if (params.dataSource) qs.set('data_source', params.dataSource);
  const res = await apiClient.post(`/alpha-agent/evolve?${qs.toString()}`);
  const data = res.data?.data ?? {};
  const taskId: string = data.task_id ?? '';
  const task = normalizeAgentTask(
    { task_id: taskId, status: data.status ?? 'pending' },
    {
      userInput: params.direction,
      numDirections: params.numDirections,
      maxRounds: loopN,
      librarySuffix: params.librarySuffix,
      qualityGateEnabled: params.qualityGateEnabled,
      parallelExecution: params.parallelEnabled,
    },
  );
  return makeOk({ taskId, task });
}

export async function getMiningStatus(
  taskId: string,
): Promise<ApiResponse<{ task: Task }>> {
  const res = await apiClient.get(`/alpha-agent/tasks/${taskId}`);
  return makeOk({ task: normalizeAgentTask(res.data?.data) });
}

export async function cancelMining(taskId: string): Promise<ApiResponse> {
  await apiClient.post(`/alpha-agent/tasks/${taskId}/cancel`);
  return makeOk({});
}

export async function listTasks(): Promise<ApiResponse<{ tasks: Task[] }>> {
  const res = await apiClient.get(`/alpha-agent/tasks`);
  const tasks: Task[] = (res.data?.data?.tasks ?? []).map((t: any) =>
    normalizeAgentTask(t),
  );
  return makeOk({ tasks });
}

// ========================== Factor API ==========================

export interface FactorListParams {
  quality?: string;
  search?: string;
  limit?: number;
  offset?: number;
  library?: string;
  market?: string;
}

export interface FactorListResponse {
  factors: Factor[];
  total: number;
  limit: number;
  offset: number;
  metadata?: any;
  libraries?: string[];
}

export async function getFactors(
  params: FactorListParams = {},
): Promise<ApiResponse<FactorListResponse>> {
  const qs = new URLSearchParams();
  // Backend caps `limit` at 200 — clamp client-side so callers requesting more
  // get the first 200 instead of a 422 validation error.
  const requested = params.limit ?? 200;
  const clamped = Math.min(Math.max(requested, 1), 200);
  qs.set('limit', String(clamped));
  if (params.market) qs.set('market', params.market);
  const res = await apiClient.get(`/alpha-agent/factors?${qs.toString()}`);
  let factors: Factor[] = (res.data?.data?.factors ?? []).map(normalizeAgentFactor);

  if (params.quality) {
    factors = factors.filter((f) => f.quality === params.quality);
  }
  if (params.search) {
    const s = params.search.toLowerCase();
    factors = factors.filter(
      (f) =>
        f.factorName.toLowerCase().includes(s) ||
        f.factorExpression.toLowerCase().includes(s) ||
        f.factorDescription.toLowerCase().includes(s),
    );
  }
  const total = factors.length;
  const offset = params.offset ?? 0;
  if (params.limit) factors = factors.slice(offset, offset + params.limit);

  return makeOk({
    factors,
    total,
    limit: params.limit ?? total,
    offset,
    libraries: ['default'],
  });
}

export async function getFactorDetail(
  factorId: string,
): Promise<ApiResponse<{ factor: any }>> {
  const res = await apiClient.get(`/alpha-agent/factors/${factorId}`);
  const raw = res.data?.data ?? {};
  return makeOk({ factor: { ...normalizeAgentFactor(raw), raw } });
}

export async function explainFactor(
  factorId: string,
): Promise<ApiResponse<{ explanation: string; cached: boolean }>> {
  const res = await apiClient.post(`/alpha-agent/factors/${factorId}/explain`);
  return makeOk(res.data?.data ?? { explanation: '', cached: false });
}

export async function listFactorLibraries(): Promise<
  ApiResponse<{ libraries: string[] }>
> {
  return makeOk({ libraries: ['default'] });
}

// ========================== Factor Cache API (no-op in QuantMind) ==========================

export interface CacheStatusResponse {
  total: number;
  h5_cached: number;
  md5_cached: number;
  need_compute: number;
  factors: Array<{
    factor_id: string;
    factor_name: string;
    status: 'h5_cached' | 'md5_cached' | 'need_compute';
  }>;
}

export interface WarmCacheResponse {
  total: number;
  synced: number;
  skipped: number;
  failed: number;
}

export async function getCacheStatus(
  _library?: string,
): Promise<ApiResponse<CacheStatusResponse>> {
  return makeOk({
    total: 0,
    h5_cached: 0,
    md5_cached: 0,
    need_compute: 0,
    factors: [],
  });
}

export async function warmCache(
  _library?: string,
): Promise<ApiResponse<WarmCacheResponse>> {
  return makeOk({ total: 0, synced: 0, skipped: 0, failed: 0 });
}

// ========================== Backtest API ==========================

export interface BacktestStartParams {
  factorJson: string;
  factorSource?: string;
  configPath?: string;
}

export async function startBacktest(
  params: BacktestStartParams,
): Promise<ApiResponse<{ taskId: string; task: Task }>> {
  let factorId = '';
  try {
    const parsed = JSON.parse(params.factorJson);
    factorId = parsed?.factorId ?? parsed?.factor_id ?? '';
  } catch {
    /* ignore */
  }
  if (!factorId) {
    return {
      success: false,
      error: '回测需要 factorId — 请在因子库中选择一个已生成的因子。',
    } as ApiResponse<any>;
  }
  const res = await apiClient.post(`/alpha-agent/factors/${factorId}/backtest`);
  const data = res.data?.data ?? {};
  const taskId = data.factor_id ?? factorId;
  return makeOk({
    taskId,
    task: normalizeAgentTask({
      task_id: taskId,
      status: data.status ?? 'running',
      progress: data.message,
    }),
  });
}

export async function getBacktestStatus(
  taskId: string,
): Promise<ApiResponse<{ task: Task }>> {
  try {
    const res = await apiClient.get(`/alpha-agent/factors/${taskId}`);
    const raw = res.data?.data ?? {};
    const status = raw.status === 'completed' ? 'completed' : 'running';
    return makeOk({
      task: normalizeAgentTask({
        task_id: taskId,
        status,
        progress: status === 'completed' ? 'Backtest done' : 'Running',
      }),
    });
  } catch {
    return makeOk({ task: normalizeAgentTask({ task_id: taskId, status: 'failed' }) });
  }
}

export async function cancelBacktest(_taskId: string): Promise<ApiResponse> {
  return makeOk({});
}

// ========================== System Config (stub) ==========================

export async function getSystemConfig(): Promise<
  ApiResponse<{
    env: Record<string, string>;
    experimentYaml: string;
    factorLibraries: string[];
  }>
> {
  return makeOk({
    env: {
      ALPHA_AGENT_BACKEND: 'QuantMind /api/v1/alpha-agent',
      NOTE: '系统配置在 QuantMind 个人中心和 .env 中管理。',
    },
    experimentYaml:
      '# AlphaAgent 实验配置由后端 launcher.py 管理\n# 如需调整，请修改 backend/services/engine/alpha_agent/ 下的 yaml 配置。\n',
    factorLibraries: ['default'],
  });
}

export async function updateSystemConfig(
  _update: Record<string, string>,
): Promise<ApiResponse> {
  return {
    success: false,
    error: '系统配置请在 QuantMind 个人中心和 .env 中修改。',
  };
}

// ========================== Health Check ==========================

export async function healthCheck(): Promise<
  ApiResponse<{ status: string; timestamp: string }>
> {
  await apiClient.get(`/alpha-agent/stats`);
  return makeOk({ status: 'ok', timestamp: new Date().toISOString() });
}

// ========================== Pseudo WebSocket via polling ==========================

export type WsCallback = (msg: WsMessage) => void;

/**
 * frontend-v2 expects a WebSocket lifecycle. AlphaAgent has no WS, so we poll
 * /alpha-agent/tasks/:id and synthesize progress/log/result messages.
 */
export function connectMiningWs(
  taskId: string,
  onMessage: WsCallback,
  onClose?: () => void,
  _onError?: (e: Event) => void,
): WebSocket {
  let stopped = false;
  let lastStatus = '';
  const fakeWs: any = {
    readyState: 1,
    send: (_data: string) => {},
    close: () => {
      stopped = true;
      fakeWs.readyState = 3;
      onClose?.();
    },
  };

  let lastPhase = '';
  let lastPct = -1;

  const poll = async () => {
    if (stopped) return;
    try {
      const res = await apiClient.get(`/alpha-agent/tasks/${taskId}`);
      const data = res.data?.data ?? {};
      const status: string = data.status ?? '';
      const backendPhase: string = typeof data.phase === 'string' ? data.phase : '';
      const progressText =
        typeof data.progress === 'string' ? data.progress : '';
      const progressPct: number =
        typeof data.progress_pct === 'number'
          ? data.progress_pct
          : status === 'completed'
            ? 100
            : status === 'running'
              ? 5
              : 0;
      const currentRound =
        typeof data.current_loop === 'number' ? data.current_loop : 0;
      const totalRounds =
        typeof data.loop_n === 'number' ? data.loop_n : 0;

      const phaseChanged = backendPhase !== lastPhase;
      const pctChanged = progressPct !== lastPct;
      const statusChanged = status !== lastStatus;

      if (statusChanged || phaseChanged || pctChanged) {
        lastStatus = status;
        lastPhase = backendPhase;
        lastPct = progressPct;
        const phase: ExecutionPhase =
          status === 'completed'
            ? 'completed'
            : PHASE_MAP[backendPhase] || 'parsing';

        onMessage({
          type: 'progress',
          taskId,
          data: {
            phase,
            currentRound,
            totalRounds,
            progress: progressPct,
            message: progressText || status,
            timestamp: new Date().toISOString(),
            timeline: data.timeline ?? undefined,
            tokenUsage: data.token_usage ?? undefined,
          },
          timestamp: new Date().toISOString(),
        });

        if (progressText && (phaseChanged || statusChanged)) {
          onMessage({
            type: 'log',
            taskId,
            data: {
              id: `${taskId}-${Date.now()}`,
              timestamp: new Date().toISOString(),
              level: status === 'failed' ? 'error' : 'info',
              message: progressText,
            },
            timestamp: new Date().toISOString(),
          });
        }

        if (status === 'completed' || status === 'failed' || status === 'cancelled') {
          onMessage({
            type: 'result',
            taskId,
            data: { status: status === 'completed' ? 'completed' : 'failed' },
            timestamp: new Date().toISOString(),
          });
          stopped = true;
          fakeWs.readyState = 3;
          onClose?.();
          return;
        }
      }
    } catch {
      /* transient — keep polling */
    }
    if (!stopped) setTimeout(poll, 1500);
  };

  setTimeout(poll, 100);
  return fakeWs as WebSocket;
}

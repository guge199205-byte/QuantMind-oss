/**
 * Strategy Lab API client.
 *
 * Endpoints (engine service):
 *   POST  /api/v1/strategy-lab/run            — sync run (blocking)
 *   POST  /api/v1/strategy-lab/run/async      — async submit
 *   GET   /api/v1/strategy-lab/run/{id}/status — SSE progress stream
 *   GET   /api/v1/strategy-lab/run/{id}/result — final RunResult
 */

import axios, { AxiosInstance } from 'axios';
import { SERVICE_URLS } from '../../../config/services';
import { authService } from '../../auth/services/authService';
import type {
  StrategyLabProgressEvent,
  StrategyLabRunRequest,
  StrategyLabRunResult,
} from '../types';

const resolveBaseUrl = () =>
  `${String(SERVICE_URLS.ENGINE_SERVICE || '').replace(/\/+$/, '')}/api/v1/strategy-lab`;

const client: AxiosInstance = axios.create({
  timeout: 120_000,
  headers: { 'Content-Type': 'application/json' },
});

client.interceptors.request.use((config) => {
  config.baseURL = resolveBaseUrl();
  const token = authService.getAccessToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

client.interceptors.response.use(
  (resp) => resp.data,
  (error) => Promise.reject(error),
);

export const strategyLabService = {
  async runSync(req: StrategyLabRunRequest): Promise<StrategyLabRunResult> {
    return (await client.post('/run', req)) as unknown as StrategyLabRunResult;
  },

  async submit(req: StrategyLabRunRequest): Promise<{ run_id: string; status: string }> {
    return (await client.post('/run/async', req)) as unknown as { run_id: string; status: string };
  },

  async fetchResult(runId: string): Promise<StrategyLabRunResult> {
    return (await client.get(`/run/${runId}/result`)) as unknown as StrategyLabRunResult;
  },

  /**
   * SSE poller — Server-Sent Events with token auth via query param fallback.
   * Returns a cleanup function. The browser EventSource cannot set Authorization
   * headers, so we poll the result endpoint and merge progress with one HTTP read.
   *
   * For simplicity in the Day-3 cut, we poll /result every 1s once we have a
   * run_id; once it's terminal we stop. This avoids the EventSource auth issue.
   */
  pollProgress(
    runId: string,
    onProgress: (evt: StrategyLabProgressEvent) => void,
    onTerminal: (result: StrategyLabRunResult | null) => void,
    intervalMs = 1000,
  ): () => void {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const tick = async () => {
      if (cancelled) return;
      try {
        const result = await strategyLabService.fetchResult(runId);
        if (cancelled) return;
        if (result && (result.status === 'success' || result.status === 'failed' || result.status === 'cancelled')) {
          onTerminal(result);
          return;
        }
        onProgress({
          run_id: runId,
          phase: 'backtest',
          pct: 50,
          message: 'running…',
          detail: {},
          ts: Date.now() / 1000,
        });
      } catch (err: any) {
        // 404 — result not yet stored, keep polling
        if (err?.response?.status !== 404) {
          if (cancelled) return;
          onTerminal(null);
          return;
        }
        onProgress({
          run_id: runId,
          phase: 'queued',
          pct: 5,
          message: 'queued…',
          detail: {},
          ts: Date.now() / 1000,
        });
      }
      if (!cancelled) {
        timer = setTimeout(tick, intervalMs);
      }
    };

    tick();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  },
};

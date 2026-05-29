import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  delete: vi.fn(),
  patch: vi.fn(),
  request: vi.fn(),
}));

vi.mock('axios', () => {
  class MockAxiosHeaders {
    set() {}
    has() { return false; }
  }

  return {
    AxiosHeaders: MockAxiosHeaders,
    default: {
      create: () => ({
        get: mocks.get,
        post: mocks.post,
        put: mocks.put,
        delete: mocks.delete,
        patch: mocks.patch,
        request: mocks.request,
        interceptors: {
          request: { use: vi.fn() },
          response: { use: vi.fn() },
        },
      }),
    },
    create: () => ({
      get: mocks.get,
      post: mocks.post,
      put: mocks.put,
      delete: mocks.delete,
      patch: mocks.patch,
      request: mocks.request,
      interceptors: {
        request: { use: vi.fn() },
        response: { use: vi.fn() },
      },
    }),
    __esModule: true,
  };
});

vi.mock('../../features/auth/services/authService', () => ({
  authService: {
    getAccessToken: vi.fn(() => 'token'),
    handle401Error: vi.fn((error: unknown) => Promise.reject(error)),
    getStoredUser: vi.fn(() => ({ user_id: '79311845' })),
  },
}));

import { realTradingService } from '../realTradingService';

describe('realTradingService manual execution APIs', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('previewManualExecution should call preview endpoint', async () => {
    mocks.request.mockResolvedValueOnce({ data: { preview_hash: 'abc', sell_orders: [], buy_orders: [], skipped_items: [], summary: {}, account_snapshot: {}, strategy_context: {} } });

    const result = await realTradingService.previewManualExecution({
      model_id: 'model_qlib',
      run_id: 'run-1',
      strategy_id: '101',
      trading_mode: 'REAL',
    });

    expect(mocks.request).toHaveBeenCalledWith(expect.objectContaining({
      method: 'post',
      url: '/manual-executions/preview',
      data: {
        model_id: 'model_qlib',
        run_id: 'run-1',
        strategy_id: '101',
        trading_mode: 'REAL',
      },
    }));
    expect(result.preview_hash).toBe('abc');
  });

  it('createManualExecution should send preview_hash to submit endpoint', async () => {
    mocks.request.mockResolvedValueOnce({ data: { status: 'success', task_id: 'manual_1' } });

    const result = await realTradingService.createManualExecution({
      model_id: 'model_qlib',
      run_id: 'run-1',
      strategy_id: '101',
      trading_mode: 'REAL',
      preview_hash: 'preview-123',
    });

    expect(mocks.request).toHaveBeenCalledWith(expect.objectContaining({
      method: 'post',
      url: '/manual-executions',
      data: {
        model_id: 'model_qlib',
        run_id: 'run-1',
        strategy_id: '101',
        trading_mode: 'REAL',
        preview_hash: 'preview-123',
      },
    }));
    expect(result.task_id).toBe('manual_1');
  });

  it('start should fall back to direct real trading endpoint when gateway request fails', async () => {
    mocks.request
      .mockRejectedValueOnce({ response: { status: 503 }, config: { url: '/start' } })
      .mockResolvedValueOnce({ data: { status: 'success', mode: 'REAL' } });

    const result = await realTradingService.start(
      '79311845',
      '101',
      'REAL',
      'default',
      { max_buy_drop: 0.05 },
      { order_type: 'LIMIT' } as any,
    );

    expect(mocks.request).toHaveBeenCalledTimes(2);
    expect(result.status).toBe('success');
  });
});

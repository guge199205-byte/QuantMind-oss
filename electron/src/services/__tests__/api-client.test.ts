import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../features/auth/services/authService', () => ({
  authService: {
    getAccessToken: vi.fn(() => null),
    handle401Error: vi.fn(async (error: unknown) => Promise.reject(error)),
  },
}));

vi.mock('axios', () => {
  const create = vi.fn();
  const isAxiosError = vi.fn(() => true);
  return {
    default: { create, isAxiosError },
    create,
    isAxiosError,
  };
});

describe('APIClient', () => {
  let APIClient: typeof import('../api-client').APIClient;
  let mockAxios: {
    get: ReturnType<typeof vi.fn>;
    post: ReturnType<typeof vi.fn>;
    put: ReturnType<typeof vi.fn>;
    delete: ReturnType<typeof vi.fn>;
    patch: ReturnType<typeof vi.fn>;
    request: ReturnType<typeof vi.fn>;
    interceptors: {
      request: { use: ReturnType<typeof vi.fn> };
      response: { use: ReturnType<typeof vi.fn> };
    };
  };
  let client: import('../api-client').APIClient;

  beforeEach(async () => {
    vi.clearAllMocks();

    mockAxios = {
      get: vi.fn(),
      post: vi.fn(),
      put: vi.fn(),
      delete: vi.fn(),
      patch: vi.fn(),
      request: vi.fn(),
      interceptors: {
        request: { use: vi.fn() },
        response: { use: vi.fn() },
      },
    };

    const axiosModule = await import('axios');
    const mockedAxios = vi.mocked(axiosModule.default, true);
    mockedAxios.create.mockReturnValue(mockAxios as unknown as any);

    const apiClientModule = await import('../api-client');
    APIClient = apiClientModule.APIClient;
    client = new APIClient({
      baseURL: 'http://localhost:3000',
      timeout: 5000,
      retries: 2,
      retryDelay: 100,
    });
  });

  it('应该创建 axios 实例并注册拦截器', async () => {
    const axiosModule = await import('axios');
    expect(vi.mocked(axiosModule.default, true).create).toHaveBeenCalled();
    expect(mockAxios.interceptors.request.use).toHaveBeenCalled();
    expect(mockAxios.interceptors.response.use).toHaveBeenCalled();
  });

  it('GET 请求应该返回 data 字段', async () => {
    mockAxios.get.mockResolvedValue({ data: { ok: true } });
    await expect(client.get('/test')).resolves.toEqual({ ok: true });
  });

  it('POST 请求应该返回 data 字段', async () => {
    mockAxios.post.mockResolvedValue({ data: { id: 1 } });
    await expect(client.post('/test', { name: 'x' })).resolves.toEqual({ id: 1 });
  });
});

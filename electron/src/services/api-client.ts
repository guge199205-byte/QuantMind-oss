/**
 * API客户端基础类
 *
 * 统一的HTTP客户端，封装请求拦截、错误处理、重试机制
 *
 * @author QuantMind Team
 * @date 2025-11-12
 */

import axios, { AxiosInstance, AxiosRequestConfig, AxiosError } from 'axios';
import { authService } from '../features/auth/services/authService';
import { normalizeBaseUrl, SERVICE_URLS } from '../config/services';

/**
 * API客户端配置接口
 */
export interface APIClientConfig {
  baseURL: string;
  timeout?: number;
  retries?: number;
  retryDelay?: number;
  onUnauthorized?: () => void;
}

/**
 * 请求错误接口
 */
export interface APIError {
  code: string;
  message: string;
  status?: number;
  data?: Record<string, unknown>;
}

/**
 * API响应包装接口
 */
export interface APIResponse<T = unknown> {
  success: boolean;
  data?: T;
  error?: APIError;
  timestamp: number;
}

/**
 * API客户端类
 *
 * 提供统一的HTTP请求接口，包含：
 * - 请求/响应拦截器
 * - 自动重试机制
 * - 错误处理
 * - Token管理
 */
export class APIClient {
  private client: AxiosInstance;
  private config: Required<APIClientConfig>;
  private baseURLOverride: string | undefined;
  private token: string | null = null;
  private retryCount: Map<string, number> = new Map();
  private tenantId: string | null = null;

  constructor(config: APIClientConfig) {
    const requestedBaseURL = normalizeBaseUrl(config.baseURL?.trim() || '');
    const currentGatewayBaseURL = normalizeBaseUrl(SERVICE_URLS.API_GATEWAY || '');
    this.baseURLOverride =
      requestedBaseURL && requestedBaseURL !== currentGatewayBaseURL
        ? requestedBaseURL
        : undefined;
    this.config = {
      timeout: config.timeout || 30000,
      retries: config.retries || 3,
      retryDelay: config.retryDelay || 1000,
      onUnauthorized: config.onUnauthorized || (() => { }),
      ...config,
    };

    this.client = axios.create({
      baseURL: this.resolveBaseURL(),
      timeout: this.config.timeout,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    this.setupInterceptors();
  }

  private getTenantId(): string {
    if (this.tenantId) return this.tenantId;
    try {
      const raw = localStorage.getItem('user');
      if (raw) {
        const u = JSON.parse(raw);
        const tid = String(u?.tenant_id || '').trim();
        if (tid) return tid;
      }
    } catch { }
    const fromEnv = String((import.meta as any).env?.VITE_TENANT_ID || '').trim();
    return fromEnv || 'default';
  }

  private resolveBaseURL(): string {
    return (
      normalizeBaseUrl(this.baseURLOverride || '') ||
      normalizeBaseUrl(SERVICE_URLS.API_GATEWAY || '')
    );
  }

  /**
   * 设置请求和响应拦截器
   */
  private setupInterceptors(): void {
    // 请求拦截器
    this.client.interceptors.request.use(
      (config) => {
        const runtimeBaseURL = this.resolveBaseURL();
        config.baseURL = runtimeBaseURL;
        this.client.defaults.baseURL = runtimeBaseURL;

        // 优先使用手动设置的Token，否则从authService获取
        const token = this.token || authService.getAccessToken();

        // 添加认证Token
        if (token) {
          if (config.headers && typeof config.headers.set === 'function') {
            config.headers.set('Authorization', `Bearer ${token}`);
          } else if (config.headers) {
            config.headers.Authorization = `Bearer ${token}`;
          }
        }

        // 多租户：默认携带 tenant_id（匿名读也需要）。
        if (config.headers && typeof config.headers.set === 'function') {
          if (!config.headers.has('X-Tenant-Id') && !config.headers.has('x-tenant-id')) {
            config.headers.set('X-Tenant-Id', this.getTenantId());
          }
        } else if (config.headers) {
          if (!config.headers['X-Tenant-Id'] && !config.headers['x-tenant-id']) {
            config.headers['X-Tenant-Id'] = this.getTenantId();
          }
        }

        // 添加请求ID用于追踪重试
        if (config.headers && typeof config.headers.set === 'function') {
          if (!config.headers.has('X-Request-ID')) {
            config.headers.set('X-Request-ID', this.generateRequestId());
          }
        } else if (config.headers) {
          if (!config.headers['X-Request-ID']) {
            config.headers['X-Request-ID'] = this.generateRequestId();
          }
        }

        return config;
      },
      (error) => {
        return Promise.reject(this.normalizeError(error));
      }
    );

    // 响应拦截器
    this.client.interceptors.response.use(
      (response) => {
        // 清除重试计数
        const requestId = response.config.headers?.['X-Request-ID'] as string;
        if (requestId) {
          this.retryCount.delete(requestId);
        }
        return response;
      },
      async (error: AxiosError) => {
        return this.handleResponseError(error);
      }
    );
  }

  /**
   * 处理响应错误
   */
  private async handleResponseError(error: AxiosError): Promise<unknown> {
    const config = error.config;
    if (!config) {
      return Promise.reject(this.normalizeError(error));
    }

    const requestId = config.headers?.['X-Request-ID'] as string;
    const currentRetry = this.retryCount.get(requestId) || 0;
    const suppressServiceUnavailableRetry = (config as any)?._suppressServiceUnavailableRetry === true;
    const status = error.response?.status;

    if (suppressServiceUnavailableRetry && status && [502, 503, 504].includes(status)) {
      this.retryCount.delete(requestId);
      return Promise.reject(this.normalizeError(error));
    }

    // 判断是否应该重试
    if (this.shouldRetry(error, currentRetry)) {
      this.retryCount.set(requestId, currentRetry + 1);

      // 计算延迟时间（指数退避）
      const delay = this.config.retryDelay * Math.pow(2, currentRetry);
      await this.sleep(delay);

      console.log(`重试请求 (${currentRetry + 1}/${this.config.retries}): ${config.url}`);
      return this.client.request(config);
    }

    // 清除重试计数
    this.retryCount.delete(requestId);

    // 处理401未授权：交由 authService 统一处理 Token 刷新与重试
    if (error.response?.status === 401) {
      this.config.onUnauthorized();
      return authService.handle401Error(error, this.client);
    }

    return Promise.reject(this.normalizeError(error));
  }

  /**
   * 判断是否应该重试
   */
  private shouldRetry(error: AxiosError, currentRetry: number): boolean {
    const suppressServiceUnavailableRetry = (error.config as any)?._suppressServiceUnavailableRetry === true;

    // 已达到最大重试次数
    if (currentRetry >= this.config.retries) {
      return false;
    }

    // 网络错误或超时错误应该重试
    if (!error.response) {
      return true;
    }

    // 5xx服务器错误应该重试，但仅限于幂等请求 (GET, HEAD, OPTIONS)
    // 对于 POST, PUT, DELETE, PATCH 等可能修改状态的请求，5xx 错误不应自动重试以避免数据重复
    const status = error.response.status;
    const method = error.config?.method?.toUpperCase();
    const idempotentMethods = ['GET', 'HEAD', 'OPTIONS'];

    if (suppressServiceUnavailableRetry && [502, 503, 504].includes(status)) {
      return false;
    }

    if (status >= 500 && status < 600) {
      return method ? idempotentMethods.includes(method) : false;
    }

    // 429请求过多应该重试
    if (status === 429) {
      return true;
    }

    return false;
  }

  /**
   * 规范化错误格式
   */
  private normalizeError(error: unknown): APIError {
    if (axios.isAxiosError(error)) {
      const axiosError = error as AxiosError;

      if (axiosError.response) {
        // 服务器响应错误
        const data = axiosError.response.data as Record<string, unknown> | undefined;
        const codeFromData = data && (data['code'] as string | undefined);
        const messageFromData = data && (data['message'] as string | undefined);
        return {
          code: codeFromData || `HTTP_${axiosError.response.status}`,
          message: messageFromData || axiosError.message || '请求失败',
          status: axiosError.response.status,
          data: data,
        };
      } else if (axiosError.request) {
        // 网络错误
        return {
          code: 'NETWORK_ERROR',
          message: '网络连接失败，请检查网络设置',
        };
      } else {
        // 请求配置错误
        return {
          code: 'REQUEST_ERROR',
          message: axiosError.message || '请求配置错误',
        };
      }
    }

    // 其他错误
    return {
      code: 'UNKNOWN_ERROR',
      message: (error as any)?.message || '未知错误',
    };
  }

  /**
   * 生成请求ID
   */
  private generateRequestId(): string {
    return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  }

  /**
   * 延迟函数
   */
  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  /**
   * 设置认证Token
   */
  setToken(token: string): void {
    this.token = token;
  }

  /**
   * 清除认证Token
   */
  clearToken(): void {
    this.token = null;
  }

  /**
   * GET请求
   */
  async get<T = unknown>(url: string, params?: Record<string, unknown>, config?: AxiosRequestConfig): Promise<T> {
    const response = await this.client.get<T>(url, {
      params,
      ...config,
    });
    return response.data;
  }

  /**
   * POST请求
   */
  async post<T = unknown>(url: string, data?: Record<string, unknown>, config?: AxiosRequestConfig): Promise<T> {
    const response = await this.client.post<T>(url, data, config);
    return response.data;
  }

  /**
   * PUT请求
   */
  async put<T = unknown>(url: string, data?: Record<string, unknown>, config?: AxiosRequestConfig): Promise<T> {
    const response = await this.client.put<T>(url, data, config);
    return response.data;
  }

  /**
   * DELETE请求
   */
  async delete<T = unknown>(url: string, config?: AxiosRequestConfig): Promise<T> {
    const response = await this.client.delete<T>(url, config);
    return response.data;
  }

  /**
   * PATCH请求
   */
  async patch<T = unknown>(url: string, data?: Record<string, unknown>, config?: AxiosRequestConfig): Promise<T> {
    const response = await this.client.patch<T>(url, data, config);
    return response.data;
  }

  /**
   * 获取原始Axios实例（用于特殊需求）
   */
  getAxiosInstance(): AxiosInstance {
    return this.client;
  }
}

/**
 * 默认配置
 */
export const DEFAULT_API_CONFIG: Partial<APIClientConfig> = {
  timeout: 30000,
  retries: 3,
  retryDelay: 1000,
};

/**
 * 创建默认API客户端实例
 */
export function createAPIClient(config: APIClientConfig): APIClient {
  return new APIClient(config);
}

/**
 * 是否导出单例实例
 */
export const apiClient = new APIClient(DEFAULT_API_CONFIG as APIClientConfig);

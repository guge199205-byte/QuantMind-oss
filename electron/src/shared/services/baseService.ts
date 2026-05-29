import { ApiResponse, RequestConfig, ApiError, ApiErrorType } from '../types/common.types';
import APIErrorHandler, { withRetry } from '../../utils/errorHandler';
import { authService } from '../../features/auth/services/authService';

import { SERVICE_URLS, normalizeBaseUrl } from '../../config/services';

export class APIClient {
  private baseURL: string;
  private defaultHeaders: Record<string, string>;

  constructor(baseURL?: string) {
    this.baseURL = baseURL || normalizeBaseUrl(SERVICE_URLS.API_GATEWAY) || SERVICE_URLS.API_GATEWAY;
    this.defaultHeaders = {
      'Content-Type': 'application/json',
    };
  }

  private async handleResponse<T>(response: Response): Promise<ApiResponse<T>> {
    // 检查响应内容是否为空
    const text = await response.text();
    const data = text ? JSON.parse(text) : {};

    if (!response.ok) {
      throw new ApiError({
        code: data.code || response.status.toString(),
        message: data.message || response.statusText,
        details: data.details,
      });
    }

    return data;
  }

  private buildURL(url: string, params?: Record<string, any>): string {
    const fullURL = url.startsWith('http') ? url : `${this.baseURL}${url}`;

    if (params) {
      const searchParams = new URLSearchParams();
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          searchParams.append(key, String(value));
        }
      });
      return `${fullURL}?${searchParams.toString()}`;
    }

    return fullURL;
  }

  private buildHeaders(headers?: Record<string, string>): Record<string, string> {
    const token = localStorage.getItem('access_token') || localStorage.getItem('auth_token');
    const authHeaders = token ? { Authorization: `Bearer ${token}` } : {};

    const combinedHeaders = {
      ...this.defaultHeaders,
      ...authHeaders,
      ...headers,
    } as Record<string, string | undefined>;

    // 过滤掉undefined值
    const filteredHeaders: Record<string, string> = {};
    Object.keys(combinedHeaders).forEach(key => {
      const value = combinedHeaders[key];
      if (value !== undefined) {
        filteredHeaders[key] = value;
      }
    });

    return filteredHeaders;
  }

  async request<T>(config: RequestConfig, isRetry = false): Promise<ApiResponse<T>> {
    const {
      url,
      method = 'GET',
      data,
      params,
      headers,
      timeout = 30000,
    } = config;

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), timeout);

      const response = await fetch(this.buildURL(url, params), {
        method,
        headers: this.buildHeaders(headers),
        body: data ? JSON.stringify(data) : undefined,
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      // 处理 401 并重试
      if (response.status === 401 && !isRetry) {
        console.warn(`[APIClient] 401错误，尝试刷新令牌并重试: ${url}`);
        const refreshToken = localStorage.getItem('refresh_token');
        if (refreshToken) {
          try {
            const newToken = await authService.getRefreshedToken(refreshToken);
            localStorage.setItem('access_token', newToken);
            // 递归重试
            return this.request<T>(config, true);
          } catch (refreshErr) {
            console.error('[APIClient] 令牌刷新失败:', refreshErr);
            // 刷新失败，交由 handleResponse 抛出原始 401
          }
        }
      }

      return this.handleResponse<T>(response);
    } catch (error) {
      if (error instanceof Error) {
        if (error.name === 'AbortError') {
          throw new ApiError({
            code: 'TIMEOUT',
            message: '请求超时',
          });
        }

        throw new ApiError({
          code: 'NETWORK_ERROR',
          message: error.message,
        });
      }

      throw error;
    }
  }

  // 便捷方法
  async get<T>(url: string, params?: Record<string, any>, headers?: Record<string, string>): Promise<ApiResponse<T>> {
    return this.request<T>({ url, method: 'GET', params, headers });
  }

  async post<T>(url: string, data?: any, headers?: Record<string, string>): Promise<ApiResponse<T>> {
    return this.request<T>({ url, method: 'POST', data, headers });
  }

  async put<T>(url: string, data?: any, headers?: Record<string, string>): Promise<ApiResponse<T>> {
    return this.request<T>({ url, method: 'PUT', data, headers });
  }

  async delete<T>(url: string, headers?: Record<string, string>): Promise<ApiResponse<T>> {
    return this.request<T>({ url, method: 'DELETE', headers });
  }

  async patch<T>(url: string, data?: any, headers?: Record<string, string>): Promise<ApiResponse<T>> {
    return this.request<T>({ url, method: 'PATCH', data, headers });
  }
}

// 基础服务抽象类
export abstract class BaseService {
  protected apiClient: APIClient;
  protected serviceName: string;

  constructor(serviceName: string, baseURL?: string) {
    this.serviceName = serviceName;
    this.apiClient = new APIClient(baseURL);
  }

  protected handleServiceError(error: any, context?: string): never {
    const fullContext = context ? `${this.serviceName}.${context}` : this.serviceName;
    const apiError = APIErrorHandler.handleError(error, fullContext);

    // 转换为项目的ApiError格式
    const serviceError = new ApiError({
      code: apiError.code,
      message: apiError.message,
      details: {
        ...apiError.details,
        suggestion: APIErrorHandler.getSuggestion(apiError),
        serviceName: this.serviceName,
        context
      },
    });

    throw serviceError;
  }

  /**
   * 带重试机制的API调用
   */
  protected async withRetry<T>(
    apiCall: () => Promise<T>,
    context?: string
  ): Promise<T> {
    const fullContext = context ? `${this.serviceName}.${context}` : this.serviceName;
    return withRetry(apiCall, fullContext);
  }

  protected logInfo(message: string, data?: any): void {
    console.info(`[${this.serviceName}] ${message}`, data);
  }

  protected logWarning(message: string, data?: any): void {
    console.warn(`[${this.serviceName}] ${message}`, data);
  }
}

// 单例模式的全局API客户端
export const globalAPIClient = new APIClient();

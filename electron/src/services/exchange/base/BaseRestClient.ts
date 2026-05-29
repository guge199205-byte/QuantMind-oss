/**
 * REST API客户端基类
 */

import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios';
import type { ExchangeConfig, ApiResponse } from './types';

export interface RequestOptions {
  method: 'GET' | 'POST' | 'PUT' | 'DELETE';
  endpoint: string;
  params?: Record<string, unknown>;
  data?: Record<string, unknown>;
  signed?: boolean;
  timeout?: number;
}

export abstract class BaseRestClient {
  protected config: ExchangeConfig;
  protected client: AxiosInstance;
  protected baseURL: string;

  constructor(config: ExchangeConfig, baseURL: string) {
    this.config = config;
    this.baseURL = baseURL;

    this.client = axios.create({
      baseURL: this.baseURL,
      timeout: config.timeout || 30000,
      headers: {
        'Content-Type': 'application/json',
        'User-Agent': 'QuantMind/1.0'
      }
    });

    this.setupInterceptors();
  }

  /**
   * 设置请求和响应拦截器
   */
  protected setupInterceptors(): void {
    this.client.interceptors.request.use(
      (config) => {
        console.log(`[REST] ${config.method?.toUpperCase()} ${config.url}`);
        return config;
      },
      (error) => {
        console.error('[REST] Request error:', error);
        return Promise.reject(error);
      }
    );

    this.client.interceptors.response.use(
      (response) => {
        console.log(`[REST] Response ${response.status} ${response.config.url}`);
        return response;
      },
      (error) => {
        console.error('[REST] Response error:', error.response?.data || error.message);
        return Promise.reject(error);
      }
    );
  }

  /**
   * 通用请求方法
   */
  protected async request<T>(options: RequestOptions): Promise<ApiResponse<T>> {
    try {
      const config: AxiosRequestConfig = {
        method: options.method,
        url: options.endpoint,
        params: options.params,
        data: options.data,
        timeout: options.timeout
      };

      // 如果需要签名
      if (options.signed) {
        await this.signRequest(config, options);
      }

      const response: AxiosResponse<T> = await this.client.request(config);

      return {
        success: true,
        data: response.data
      };
    } catch (error: unknown) {
      const resp = (error as { response?: { status?: number; data?: { msg?: string; message?: string } } })?.response;
      const code = resp?.status?.toString?.() ?? 'UNKNOWN';
      const message = resp?.data?.msg ?? resp?.data?.message ?? (error as Error).message ?? String(error);
      return {
        success: false,
        error: {
          code,
          message
        }
      };
    }
  }

  /**
   * GET请求
   */
  protected async get<T>(
    endpoint: string,
    params?: Record<string, unknown>,
    signed: boolean = false
  ): Promise<ApiResponse<T>> {
    return this.request<T>({
      method: 'GET',
      endpoint,
      params,
      signed
    });
  }

  /**
   * POST请求
   */
  protected async post<T>(
    endpoint: string,
    data?: Record<string, unknown>,
    signed: boolean = false
  ): Promise<ApiResponse<T>> {
    return this.request<T>({
      method: 'POST',
      endpoint,
      data,
      signed
    });
  }

  /**
   * DELETE请求
   */
  protected async delete<T>(
    endpoint: string,
    params?: Record<string, unknown>,
    signed: boolean = false
  ): Promise<ApiResponse<T>> {
    return this.request<T>({
      method: 'DELETE',
      endpoint,
      params,
      signed
    });
  }

  /**
   * 签名请求（子类实现）
   */
  protected abstract signRequest(
    config: AxiosRequestConfig,
    options: RequestOptions
  ): Promise<void>;

  /**
   * 生成查询字符串
   */
  protected buildQueryString(params: Record<string, unknown>): string {
    return Object.keys(params)
      .sort()
      .map(key => `${key}=${encodeURIComponent(String((params as Record<string, unknown>)[key]))}`)
      .join('&');
  }
}

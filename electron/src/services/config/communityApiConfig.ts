/**
 * 社区API配置
 * Community API Configuration
 *
 * 集中管理社区相关的API配置
 *
 * @author QuantMind Team
 * @date 2025-11-19
 */

import { SERVICE_URLS, normalizeBaseUrl } from '../../config/services';

/**
 * API配置
 */
export const COMMUNITY_API_CONFIG = {
  // API基础地址
  BASE_URL: SERVICE_URLS.API_GATEWAY,

  // API版本
  API_VERSION: 'v1',

  // 超时设置（毫秒）
  TIMEOUT: 30000,

  // 重试次数
  RETRIES: 2,

  // 是否启用Mock数据
  USE_MOCK: import.meta.env.VITE_USE_MOCK_DATA === 'true',

  // 分页配置
  PAGINATION: {
    DEFAULT_PAGE_SIZE: 20,
    MAX_PAGE_SIZE: 100,
  },

  // 缓存配置
  CACHE: {
    ENABLED: true,
    TTL: 5 * 60 * 1000, // 5分钟
  },
};

/**
 * API端点
 */
export const COMMUNITY_API_ENDPOINTS = {
  // 帖子相关
  POSTS: {
    LIST: '/community/posts',
    DETAIL: (id: number) => `/community/posts/${id}`,
    CREATE: '/community/posts',
    UPDATE: (id: number) => `/community/posts/${id}`,
    DELETE: (id: number) => `/community/posts/${id}`,
    LIKE: (id: number) => `/community/posts/${id}/like`,
    COLLECT: (id: number) => `/community/posts/${id}/collect`,
  },

  // 评论相关
  COMMENTS: {
    LIST: (postId: number) => `/community/posts/${postId}/comments`,
    CREATE: (postId: number) => `/community/posts/${postId}/comments`,
    DELETE: (id: number) => `/community/comments/${id}`,
  },

  // 热门数据
  HOT: {
    USERS: '/community/hot-users',
    TOPICS: '/community/hot-topics',
  },

  // 搜索
  SEARCH: '/community/search',
};

/**
 * API状态码
 */
export const API_STATUS_CODES = {
  SUCCESS: 200,
  CREATED: 201,
  NO_CONTENT: 204,
  BAD_REQUEST: 400,
  UNAUTHORIZED: 401,
  FORBIDDEN: 403,
  NOT_FOUND: 404,
  SERVER_ERROR: 500,
};

/**
 * 错误消息映射
 */
export const ERROR_MESSAGES = {
  NETWORK_ERROR: '网络连接失败，请检查您的网络设置',
  TIMEOUT: '请求超时，请稍后重试',
  UNAUTHORIZED: '请先登录',
  FORBIDDEN: '没有权限执行此操作',
  NOT_FOUND: '请求的资源不存在',
  SERVER_ERROR: '服务器错误，请稍后重试',
  UNKNOWN: '未知错误，请联系管理员',
};

/**
 * 请求头配置
 */
export const REQUEST_HEADERS = {
  'Content-Type': 'application/json',
  'Accept': 'application/json',
};

/**
 * 获取完整的API URL
 */
export function getFullAPIUrl(endpoint: string): string {
  const { BASE_URL, API_VERSION } = COMMUNITY_API_CONFIG;
  const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  return `${BASE_URL}/api/${API_VERSION}${cleanEndpoint}`;
}

/**
 * 获取认证Token
 */
export function getAuthToken(): string | null {
  // 从localStorage或其他存储中获取token
  return localStorage.getItem('auth_token');
}

/**
 * 获取认证请求头
 */
export function getAuthHeaders(): Record<string, string> {
  const token = getAuthToken();
  return token ? { 'Authorization': `Bearer ${token}` } : {};
}

/**
 * 构建完整的请求头
 */
export function buildHeaders(customHeaders: Record<string, string> = {}): Record<string, string> {
  return {
    ...REQUEST_HEADERS,
    ...getAuthHeaders(),
    ...customHeaders,
  };
}

export default {
  config: COMMUNITY_API_CONFIG,
  endpoints: COMMUNITY_API_ENDPOINTS,
  statusCodes: API_STATUS_CODES,
  errorMessages: ERROR_MESSAGES,
  getFullAPIUrl,
  getAuthToken,
  getAuthHeaders,
  buildHeaders,
};

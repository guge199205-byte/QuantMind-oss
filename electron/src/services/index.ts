/**
 * 服务层导出
 *
 * 统一导出所有服务和创建服务实例
 *
 * @author QuantMind Team
 * @date 2025-11-12
 */

import { APIClient, createAPIClient, APIClientConfig } from './api-client';

/**
 * 默认API配置
 */
const DEFAULT_CONFIG: Partial<APIClientConfig> = {
  timeout: 30000,
  retries: 3,
  retryDelay: 1000,
};

/**
 * 创建默认服务实例
 */
let apiClientInstance: APIClient | null = null;

/**
 * 获取API客户端实例（单例）
 */
export function getAPIClient(): APIClient {
  if (!apiClientInstance) {
    apiClientInstance = createAPIClient(DEFAULT_CONFIG as APIClientConfig);
  }
  return apiClientInstance;
}

/**
 * 重置服务实例（用于测试或重新配置）
 */
export function resetServices(): void {
  apiClientInstance = null;
}

/**
 * 使用自定义配置创建服务
 */
export function createServices(config: Partial<APIClientConfig>) {
  const fullConfig = { ...DEFAULT_CONFIG, ...config };
  const client = createAPIClient(fullConfig as APIClientConfig);

  return {
    apiClient: client,
  };
}

// 导出所有类型和接口
export * from './api-client';

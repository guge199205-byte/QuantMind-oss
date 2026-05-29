/**
 * 本地存储配置 (OSS Edition)
 * 云存储已禁用，使用本地存储
 */

import { SERVICE_URLS } from './services';

export interface StorageConfig {
  baseUrl: string;
  enabled: boolean;
}

/**
 * 获取本地存储配置
 */
export const getStorageConfig = (): StorageConfig => {
  const baseUrl = SERVICE_URLS.API_GATEWAY || '';
  return {
    baseUrl,
    enabled: true
  };
};

/**
 * 获取存储配置
 */
export const validateStorageConfig = (config: StorageConfig): boolean => {
  return config.enabled;
};

/**
 * 获取文件命名规则
 */
export const generateFileName = (
  strategyType: string,
  fileName: string,
  timestamp: number = Date.now()
): string => {
  const date = new Date(timestamp);
  const dateStr = date.toISOString().replace(/[:.]/g, '-').replace('T', '_');
  const randomStr = Math.random().toString(36).substr(2, 8);

  const strategyTypeMap: Record<string, string> = {
    'moving_average': '均线策略',
    'momentum': '动量策略',
    'breakout': '突破策略',
    'arbitrage': '套利策略',
    'grid': '网格策略',
    'custom': '自定义策略'
  };

  const typeName = strategyTypeMap[strategyType] || strategyType;

  return `strategies/${strategyType}/${dateStr}_${randomStr}_${typeName}_${fileName}`;
};

/**
 * 默认存储配置
 */
export const defaultStorageConfig: StorageConfig = {
  baseUrl: '',
  enabled: true
};

export default getStorageConfig;

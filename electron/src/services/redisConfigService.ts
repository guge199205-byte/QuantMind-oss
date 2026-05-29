/**
 * Redis配置API服务
 * 
 * 处理Redis连接配置获取和密码修改
 */

import { createAPIClient } from './api-client';
import { SERVICE_ENDPOINTS } from '../config/services';

const apiClient = createAPIClient({
  baseURL: SERVICE_ENDPOINTS.TRADING,
});

// 设置用户ID到请求头
export const setUserId = (userId: string) => {
  apiClient.getAxiosInstance().defaults.headers.common['X-User-Id'] = userId;
};

/**
 * Redis配置响应接口
 */
export interface RedisConfig {
  host: string;
  port: number;
  username: string;
  user_id: string;
}

/**
 * 密码修改请求接口
 */
export interface ChangePasswordRequest {
  old_password: string;
  new_password: string;
}

/**
 * API响应接口
 */
interface APIResponse<T = any> {
  code: number;
  message: string;
  data: T;
}

/**
 * 获取Redis连接配置
 */
export const getRedisConfig = async (): Promise<RedisConfig> => {
  try {
    const response = await apiClient.get<APIResponse<RedisConfig>>('/redis-config');
    if (response.code === 200) {
      return response.data;
    }
    throw new Error(response.message || '获取配置失败');
  } catch (error: any) {
    console.error('获取Redis配置失败:', error);
    throw new Error(error.message || '获取配置失败');
  }
};

/**
 * 修改Redis密码
 */
export const changeRedisPassword = async (
  oldPassword: string,
  newPassword: string
): Promise<void> => {
  try {
    const response = await apiClient.post<APIResponse>('/redis-config/change-password', {
      old_password: oldPassword,
      new_password: newPassword,
    });
    
    if (response.code === 200) {
      return;
    }
    throw new Error(response.message || '密码修改失败');
  } catch (error: any) {
    console.error('修改密码失败:', error);
    
    // 处理特定错误
    if (error.response?.status === 400) {
      throw new Error('当前密码错误');
    }
    if (error.response?.status === 401) {
      throw new Error('用户未认证，请重新登录');
    }
    
    throw new Error(error.message || '密码修改失败，请稍后重试');
  }
};

export default {
  getRedisConfig,
  changeRedisPassword,
  setUserId,
};

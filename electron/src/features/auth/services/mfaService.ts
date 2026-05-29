/**
 * MFA服务API
 * 处理多因素认证相关的网络请求
 */

import axios, { AxiosInstance, AxiosResponse } from 'axios';
import { authService } from './authService';
import { SERVICE_ENDPOINTS } from '../../../config/services';

// API响应类型
export interface ApiResponse<T = any> {
  success: boolean;
  data?: T;
  message?: string;
  status_code?: number;
}

// MFA设置请求类型
export interface MFASetupRequest { }

// MFA验证请求类型
export interface MFAVerifyRequest {
  verification_code: string;
}

// MFA禁用请求类型
export interface MFADisableRequest {
  password: string;
}

// MFA登录验证请求类型
export interface MFALoginVerifyRequest {
  verification_code: string;
  temp_token: string;
}

// MFA状态类型
export interface MFAStatus {
  enabled: boolean;
  setup_completed: boolean;
  enabled_date?: string;
  remaining_backup_codes?: number;
  last_used_backup_code?: string;
  error?: string;
}

// MFA设置数据类型
export interface MFASetupData {
  secret: string;
  qr_code: string;
  backup_codes: string[];
  manual_entry_key: string;
  instructions: {
    step1: string;
    step2: string;
    step3: string;
    step4: string;
  };
}

/**
 * MFA服务类
 */
class MFAService {
  private axiosInstance: AxiosInstance;

  constructor() {
    this.axiosInstance = axios.create({
      baseURL: `${SERVICE_ENDPOINTS.USER_SERVICE}/auth/mfa`,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    this.setupInterceptors();
  }

  /**
   * 设置拦截器
   */
  private setupInterceptors(): void {
    // 请求拦截器 - 添加认证token
    this.axiosInstance.interceptors.request.use(
      (config) => {
        const token = authService.getAccessToken();
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        console.log(`[MFA Request] ${config.method?.toUpperCase()} ${config.url}`, config.data);
        return config;
      },
      (error) => {
        console.error('[MFA Request Error]', error);
        return Promise.reject(error);
      }
    );

    // 响应拦截器
    this.axiosInstance.interceptors.response.use(
      (response: AxiosResponse) => {
        console.log(`[MFA Response] ${response.config.url}`, response.data);
        return response;
      },
      async (error) => {
        console.error('[MFA Response Error]', error);

        // 处理401未授权错误 - 交由 authService 统一处理 Token 刷新与重试
        if (error.response?.status === 401) {
          return authService.handle401Error(error, this.axiosInstance);
        }

        return Promise.reject(this.handleError(error));
      }
    );
  }

  /**
   * 处理错误
   */
  private handleError(error: any): Error {
    let message = '未知错误';

    if (error.response) {
      // 服务器返回错误
      const status = error.response.status;
      const data = error.response.data;

      switch (status) {
        case 400:
          message = data?.message || '请求参数错误';
          break;
        case 401:
          message = data?.message || '未授权，请重新登录';
          break;
        case 403:
          message = data?.message || '禁止访问';
          break;
        case 404:
          message = data?.message || '资源不存在';
          break;
        case 429:
          message = '请求过于频繁，请稍后再试';
          break;
        case 500:
          message = data?.message || '服务器内部错误';
          break;
        default:
          message = data?.message || `请求失败 (${status})`;
      }
    } else if (error.request) {
      // 网络错误
      message = '网络连接失败，请检查网络设置';
    } else {
      // 其他错误
      message = error.message || '操作失败';
    }

    return new Error(message);
  }

  /**
   * 设置MFA
   */
  async setupMFA(): Promise<ApiResponse<MFASetupData>> {
    try {
      const response = await this.axiosInstance.post<ApiResponse<MFASetupData>>('/setup');
      return response.data;
    } catch (error) {
      console.error('设置MFA失败:', error);
      throw error;
    }
  }

  /**
   * 验证并启用MFA
   */
  async verifyAndEnableMFA(request: MFAVerifyRequest): Promise<ApiResponse> {
    try {
      const response = await this.axiosInstance.post<ApiResponse>('/verify-and-enable', request);
      return response.data;
    } catch (error) {
      console.error('验证MFA失败:', error);
      throw error;
    }
  }

  /**
   * 验证MFA登录
   */
  async verifyMFALogin(request: MFALoginVerifyRequest): Promise<ApiResponse> {
    try {
      // 使用不认证的axios实例，因为此时还没有正式token
      const response = await axios.post<ApiResponse>(
        `${SERVICE_ENDPOINTS.USER_SERVICE}/auth/mfa/login-verify`,
        request,
        {
          timeout: 30000,
          headers: {
            'Content-Type': 'application/json',
          },
        }
      );
      return response.data;
    } catch (error) {
      console.error('MFA登录验证失败:', error);
      throw error;
    }
  }

  /**
   * 禁用MFA
   */
  async disableMFA(request: MFADisableRequest): Promise<ApiResponse> {
    try {
      const response = await this.axiosInstance.post<ApiResponse>('/disable', request);
      return response.data;
    } catch (error) {
      console.error('禁用MFA失败:', error);
      throw error;
    }
  }

  /**
   * 获取MFA状态
   */
  async getMFAStatus(): Promise<ApiResponse<MFAStatus>> {
    try {
      const response = await this.axiosInstance.get<ApiResponse<MFAStatus>>('/status');
      return response.data;
    } catch (error) {
      console.error('获取MFA状态失败:', error);
      throw error;
    }
  }

  /**
   * 重新生成备用恢复码
   */
  async regenerateBackupCodes(): Promise<ApiResponse<{ backup_codes: string[]; message: string }>> {
    try {
      const response = await this.axiosInstance.post<ApiResponse<{ backup_codes: string[]; message: string }>>(
        '/regenerate-backup-codes'
      );
      return response.data;
    } catch (error) {
      console.error('重新生成备用码失败:', error);
      throw error;
    }
  }

  /**
   * 检查MFA是否启用
   */
  async isMFAEnabled(): Promise<boolean> {
    try {
      const response = await this.getMFAStatus();
      // getMFAStatus returns ApiResponse<MFAStatus>
      return (response.success && response.data?.enabled) || false;
    } catch (error) {
      console.error('检查MFA状态失败:', error);
      return false;
    }
  }

  /**
   * 验证备用恢复码格式
   */
  validateBackupCode(code: string): boolean {
    // 备用码通常是8位字母数字组合
    return /^[A-F0-9]{8}$/i.test(code);
  }

  /**
   * 验证TOTP码格式
   */
  validateTOTPCode(code: string): boolean {
    // TOTP码是6位数字
    return /^\d{6}$/.test(code);
  }

  /**
   * 格式化备用码显示
   */
  formatBackupCode(code: string): string {
    // 将8位备用码格式化为4-4格式: ABCD-EFGH
    if (code.length === 8) {
      return `${code.slice(0, 4)}-${code.slice(4)}`;
    }
    return code;
  }

  /**
   * 生成MFA设置说明
   */
  generateSetupInstructions(): {
    title: string;
    steps: Array<{
      title: string;
      description: string;
      icon: string;
    }>;
    tips: string[];
  } {
    return {
      title: '多因素认证设置指南',
      steps: [
        {
          title: '下载认证应用',
          description: '在手机上安装Google Authenticator、Microsoft Authenticator或类似应用',
          icon: 'mobile',
        },
        {
          title: '扫描二维码',
          description: '使用认证应用扫描屏幕上显示的二维码，或手动输入密钥',
          icon: 'qrcode',
        },
        {
          title: '输入验证码',
          description: '输入认证应用显示的6位数字验证码以完成设置',
          icon: 'key',
        },
        {
          title: '保存备用码',
          description: '将生成的备用恢复码保存在安全的地方，以备不时之需',
          icon: 'safety',
        },
      ],
      tips: [
        '备用恢复码是您无法使用认证应用时的最后手段',
        '每个备用码只能使用一次，使用后请立即生成新的备用码',
        '建议将备用码打印或保存在离线安全的地方',
        '请确保手机时间准确，否则验证码可能无法正常工作',
      ],
    };
  }
}

// 导出单例实例
export const mfaService = new MFAService();

// 导出默认实例
export default mfaService;

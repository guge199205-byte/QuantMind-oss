/**
 * 认证相关自定义Hooks
 */

import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAppDispatch, useAppSelector } from '../../../store';
import {
  initializeAuth,
  login,
  register,
  logout,
  refreshToken,
  updateLastActivity,
  updateLoginForm,
  updateRegisterForm,
  setLoginFormErrors,
  clearLoginFormErrors,
  setRegisterFormErrors,
  clearRegisterFormErrors,
  resetLoginForm,
  resetRegisterForm,
} from '../store/authSlice';
import type { LoginCredentials, RegisterData } from '../types/auth.types';

// ============ 主要认证Hook ============

/**
 * 认证状态管理Hook
 */
export const useAuth = () => {
  const dispatch = useAppDispatch();
  const navigate = useNavigate();

  const authState = useAppSelector((state) => state.auth);

  console.log('[useAuth] 当前认证状态:', {
    isAuthenticated: authState.isAuthenticated,
    isLoading: authState.isLoading,
    hasUser: !!authState.user,
    hasError: !!authState.error
  });

  // 初始化认证状态
  useEffect(() => {
    if (!authState.isInitialized) {
      console.log('[useAuth] 开始初始化认证状态');
      dispatch(initializeAuth());
    }
  }, [dispatch, authState.isInitialized]);

  // 自动刷新令牌
  useEffect(() => {
    if (!authState.isAuthenticated || !authState.tokenExpiryTime) {
      return;
    }

    // 计算令牌过期时间前5分钟开始刷新
    const refreshTime = authState.tokenExpiryTime - 5 * 60 * 1000;
    const now = Date.now();

    if (now < refreshTime) {
      const timeout = setTimeout(() => {
        dispatch(refreshToken());
      }, refreshTime - now);

      return () => clearTimeout(timeout);
    }
  }, [authState.isAuthenticated, authState.tokenExpiryTime, dispatch]);

  // 活动时间更新（优化：减少频率，避免过度渲染）
  useEffect(() => {
    let lastUpdateTime = 0;
    const UPDATE_THROTTLE = 60000; // 每分钟最多更新一次

    const updateActivity = () => {
      const now = Date.now();
      // 节流：至少间隔1分钟才更新一次
      if (now - lastUpdateTime > UPDATE_THROTTLE) {
        lastUpdateTime = now;
        dispatch(updateLastActivity());
      }
    };

    // 监听用户活动
    const events = ['mousedown', 'keypress'];  // 减少监听事件
    events.forEach(event => {
      window.addEventListener(event, updateActivity);
    });

    return () => {
      events.forEach(event => {
        window.removeEventListener(event, updateActivity);
      });
    };
  }, [dispatch]);

  // 登录
  const handleLogin = async (credentials: LoginCredentials) => {
    const result = await dispatch(login(credentials)).unwrap();
    return result;
  };

  // 注册
  const handleRegister = async (userData: RegisterData) => {
    const result = await dispatch(register(userData)).unwrap();
    return result;
  };

  // 登出
  const handleLogout = async () => {
    try {
      await dispatch(logout()).unwrap();
      navigate('/auth/login');
    } catch (error) {
      console.error('登出失败:', error);
      // 即使失败也要跳转到登录页
      navigate('/auth/login');
    }
  };

  return {
    // 状态
    ...authState,

    // 操作
    login: handleLogin,
    register: handleRegister,
    logout: handleLogout,

    // 工具方法
    isAuthenticated: authState.isAuthenticated,
    isLoading: authState.isLoading,
    hasError: !!authState.error,
    error: authState.error,
  };
};

// ============ 登录表单Hook ============

/**
 * 登录表单管理Hook
 */
export const useLoginForm = () => {
  const dispatch = useAppDispatch();
  const loginForm = useAppSelector((state) => state.auth.loginForm);
  const isLoading = useAppSelector((state) => state.auth.loginForm.isSubmitting);
  const error = useAppSelector((state) => state.auth.error);

  const updateField = (field: string, value: any) => {
    dispatch(updateLoginForm({ field, value }));
  };

  const setErrors = (errors: Record<string, string>) => {
    dispatch(setLoginFormErrors(errors));
  };

  const clearErrors = () => {
    dispatch(clearLoginFormErrors());
  };

  const reset = () => {
    dispatch(resetLoginForm());
  };

  return {
    // 状态
    ...loginForm,
    isLoading,
    error,

    // 操作
    updateField,
    setErrors,
    clearErrors,
    reset,

    // 便捷方法
    setEmail: (email: string) => updateField('email_or_username', email),
    setPassword: (password: string) => updateField('password', password),
    setRememberMe: (remember: boolean) => updateField('remember_me', remember),
  };
};

// ============ 注册表单Hook ============

/**
 * 注册表单管理Hook
 */
export const useRegisterForm = () => {
  const dispatch = useAppDispatch();
  const registerForm = useAppSelector((state) => state.auth.registerForm);
  const isLoading = useAppSelector((state) => state.auth.registerForm.isSubmitting);
  const error = useAppSelector((state) => state.auth.error);

  const updateField = (field: string, value: any) => {
    dispatch(updateRegisterForm({ field, value }));
  };

  const setErrors = (errors: Record<string, string>) => {
    dispatch(setRegisterFormErrors(errors));
  };

  const clearErrors = () => {
    dispatch(clearRegisterFormErrors());
  };

  const reset = () => {
    dispatch(resetRegisterForm());
  };

  return {
    // 状态
    ...registerForm,
    isLoading,
    error,

    // 操作
    updateField,
    setErrors,
    clearErrors,
    reset,

    // 便捷方法
    setEmail: (email: string) => updateField('email', email),
    setPassword: (password: string) => updateField('password', password),
    setConfirmPassword: (confirmPassword: string) => updateField('confirmPassword', confirmPassword),
    setFullName: (fullName: string) => updateField('full_name', fullName),
    setPhone: (phone: string) => updateField('phone', phone),
    setSmsVerificationCode: (code: string) => updateField('sms_verification_code', code),
  };
};

// ============ 权限检查Hook ============

/**
 * 检查用户是否已认证
 */
export const useRequireAuth = () => {
  const { isAuthenticated, isLoading, user } = useAuth();

  return {
    isAuthenticated,
    isLoading,
    user,
  };
};

/**
 * 检查用户角色权限
 */
export const useRequireRole = (requiredRole?: string) => {
  const { user, isAuthenticated, isLoading } = useAuth();

  const hasRole = requiredRole ? user?.is_admin : true;

  return {
    hasRole: hasRole || false,
    isAuthenticated,
    isLoading,
    user,
  };
};

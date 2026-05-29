/**
 * 用户配置Hooks
 */

import { useEffect, useCallback } from 'react';
import { useAppDispatch, useAppSelector } from '../../../store';
import type { RootState } from '../../../store';
import {
  fetchUserConfig,
  updateUserConfig,
  updateNotificationSettings,
  updatePrivacySettings,
} from '../store/configSlice';
import type { UserConfig, NotificationSettings, PrivacySettings } from '../types';

// ============ 用户配置Hook ============

/**
 * 使用用户配置
 * @param userId 用户ID
 * @param autoFetch 是否自动获取
 */
export const useUserConfig = (userId: string, autoFetch = true) => {
  const dispatch = useAppDispatch();
  const config = useAppSelector((state: RootState) => state.config.config);
  const isLoading = useAppSelector((state: RootState) => state.config.isLoading);
  const error = useAppSelector((state: RootState) => state.config.error);
  const updateStatus = useAppSelector((state: RootState) => state.config.updateStatus);

  useEffect(() => {
    if (autoFetch && userId) {
      dispatch(fetchUserConfig(userId));
    }
  }, [dispatch, userId, autoFetch]);

  const handleUpdateConfig = useCallback(
    async (data: Partial<UserConfig>) => {
      return dispatch(updateUserConfig({ userId, data })).unwrap();
    },
    [dispatch, userId]
  );

  const refetch = useCallback(() => {
    dispatch(fetchUserConfig(userId));
  }, [dispatch, userId]);

  return {
    config,
    isLoading,
    error,
    updateStatus,
    updateConfig: handleUpdateConfig,
    refetch,
  };
};

// ============ 通知设置Hook ============

/**
 * 使用通知设置
 * @param userId 用户ID
 */
export const useNotificationSettings = (userId: string) => {
  const dispatch = useAppDispatch();
  const notificationSettings = useAppSelector((state: RootState) => state.config.config?.notification_settings);
  const updateStatus = useAppSelector((state: RootState) => state.config.updateStatus);
  const error = useAppSelector((state: RootState) => state.config.error);

  const handleUpdateSettings = useCallback(
    async (settings: Partial<NotificationSettings>) => {
      return dispatch(updateNotificationSettings({ userId, settings })).unwrap();
    },
    [dispatch, userId]
  );

  return {
    settings: notificationSettings,
    updateStatus,
    error,
    updateSettings: handleUpdateSettings,
  };
};

// ============ 隐私设置Hook ============

/**
 * 使用隐私设置
 * @param userId 用户ID
 */
export const usePrivacySettings = (userId: string) => {
  const dispatch = useAppDispatch();
  const privacySettings = useAppSelector((state: RootState) => state.config.config?.privacy_settings);
  const updateStatus = useAppSelector((state: RootState) => state.config.updateStatus);
  const error = useAppSelector((state: RootState) => state.config.error);

  const handleUpdateSettings = useCallback(
    async (settings: Partial<PrivacySettings>) => {
      return dispatch(updatePrivacySettings({ userId, settings })).unwrap();
    },
    [dispatch, userId]
  );

  return {
    settings: privacySettings,
    updateStatus,
    error,
    updateSettings: handleUpdateSettings,
  };
};

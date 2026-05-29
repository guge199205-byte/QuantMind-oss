/**
 * 用户配置Redux Slice
 */

import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import { userCenterService } from '../services/userCenterService';
import type {
  UserConfig,
  NotificationSettings,
  PrivacySettings,
  LoadingState,
} from '../types';

// ============ 状态接口定义 ============

export interface ConfigState {
  config: UserConfig | null;
  isLoading: boolean;
  error: string | null;
  updateStatus: LoadingState;
}

// ============ 初始状态 ============

const initialState: ConfigState = {
  config: null,
  isLoading: false,
  error: null,
  updateStatus: 'idle',
};

// ============ 异步Thunk ============

/**
 * 获取用户配置
 */
export const fetchUserConfig = createAsyncThunk(
  'config/fetchUserConfig',
  async (userId: string, { rejectWithValue }) => {
    try {
      const MAX_RETRIES = 3;
      let attempt = 0;
      let lastError: any = null;
      while (attempt < MAX_RETRIES) {
        try {
          const config = await userCenterService.getUserConfig(userId);
          return config;
        } catch (e: any) {
          lastError = e;
          await new Promise((r) => setTimeout(r, 300 * (attempt + 1)));
          attempt++;
        }
      }
      const msg = lastError?.message || 'Network Error: No response from server';
      return rejectWithValue(msg);
    } catch (error: any) {
      return rejectWithValue(error.message || 'Failed to fetch user config');
    }
  }
);

/**
 * 更新用户配置
 */
export const updateUserConfig = createAsyncThunk(
  'config/updateUserConfig',
  async (
    { userId, data }: { userId: string; data: Partial<UserConfig> },
    { rejectWithValue }
  ) => {
    try {
      const config = await userCenterService.updateUserConfig(userId, data);
      return config;
    } catch (error: any) {
      return rejectWithValue(error.message || 'Failed to update user config');
    }
  }
);

/**
 * 更新通知设置
 */
export const updateNotificationSettings = createAsyncThunk(
  'config/updateNotificationSettings',
  async (
    { userId, settings }: { userId: string; settings: Partial<NotificationSettings> },
    { rejectWithValue, getState }
  ) => {
    try {
      const state = getState() as { config: ConfigState };
      const currentConfig = state.config.config;

      if (!currentConfig) {
        throw new Error('Config not loaded');
      }

      const updatedConfig = {
        ...currentConfig,
        notification_settings: {
          ...currentConfig.notification_settings,
          ...settings,
        },
      };

      const config = await userCenterService.updateUserConfig(userId, updatedConfig);
      return config;
    } catch (error: any) {
      return rejectWithValue(error.message || 'Failed to update notification settings');
    }
  }
);

/**
 * 更新隐私设置
 */
export const updatePrivacySettings = createAsyncThunk(
  'config/updatePrivacySettings',
  async (
    { userId, settings }: { userId: string; settings: Partial<PrivacySettings> },
    { rejectWithValue, getState }
  ) => {
    try {
      const state = getState() as { config: ConfigState };
      const currentConfig = state.config.config;

      if (!currentConfig) {
        throw new Error('Config not loaded');
      }

      const updatedConfig = {
        ...currentConfig,
        privacy_settings: {
          ...currentConfig.privacy_settings,
          ...settings,
        },
      };

      const config = await userCenterService.updateUserConfig(userId, updatedConfig);
      return config;
    } catch (error: any) {
      return rejectWithValue(error.message || 'Failed to update privacy settings');
    }
  }
);

// ============ Slice定义 ============

export const configSlice = createSlice({
  name: 'config',
  initialState,
  reducers: {
    /**
     * 重置状态
     */
    resetConfig: (state) => {
      return initialState;
    },

    /**
     * 清除错误
     */
    clearError: (state) => {
      state.error = null;
    },

    /**
     * 重置更新状态
     */
    resetUpdateStatus: (state) => {
      state.updateStatus = 'idle';
    },

    /**
     * 更新本地配置（无需API调用）
     */
    updateLocalConfig: (state, action: PayloadAction<Partial<UserConfig>>) => {
      if (state.config) {
        state.config = {
          ...state.config,
          ...action.payload,
          updated_at: new Date().toISOString(),
        };
      }
    },

    /**
     * 更新本地通知设置
     */
    updateLocalNotificationSettings: (
      state,
      action: PayloadAction<Partial<NotificationSettings>>
    ) => {
      if (state.config) {
        state.config.notification_settings = {
          ...state.config.notification_settings,
          ...action.payload,
        };
        state.config.updated_at = new Date().toISOString();
      }
    },

    /**
     * 更新本地隐私设置
     */
    updateLocalPrivacySettings: (
      state,
      action: PayloadAction<Partial<PrivacySettings>>
    ) => {
      if (state.config) {
        state.config.privacy_settings = {
          ...state.config.privacy_settings,
          ...action.payload,
        };
        state.config.updated_at = new Date().toISOString();
      }
    },
  },
  extraReducers: (builder) => {
    // ===== 获取用户配置 =====
    builder
      .addCase(fetchUserConfig.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(fetchUserConfig.fulfilled, (state, action) => {
        state.isLoading = false;
        state.config = action.payload;
        state.error = null;
      })
      .addCase(fetchUserConfig.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      });

    // ===== 更新用户配置 =====
    builder
      .addCase(updateUserConfig.pending, (state) => {
        state.updateStatus = 'loading';
        state.error = null;
      })
      .addCase(updateUserConfig.fulfilled, (state, action) => {
        state.updateStatus = 'success';
        state.config = action.payload;
        state.error = null;
      })
      .addCase(updateUserConfig.rejected, (state, action) => {
        state.updateStatus = 'error';
        state.error = action.payload as string;
      });

    // ===== 更新通知设置 =====
    builder
      .addCase(updateNotificationSettings.pending, (state) => {
        state.updateStatus = 'loading';
        state.error = null;
      })
      .addCase(updateNotificationSettings.fulfilled, (state, action) => {
        state.updateStatus = 'success';
        state.config = action.payload;
        state.error = null;
      })
      .addCase(updateNotificationSettings.rejected, (state, action) => {
        state.updateStatus = 'error';
        state.error = action.payload as string;
      });

    // ===== 更新隐私设置 =====
    builder
      .addCase(updatePrivacySettings.pending, (state) => {
        state.updateStatus = 'loading';
        state.error = null;
      })
      .addCase(updatePrivacySettings.fulfilled, (state, action) => {
        state.updateStatus = 'success';
        state.config = action.payload;
        state.error = null;
      })
      .addCase(updatePrivacySettings.rejected, (state, action) => {
        state.updateStatus = 'error';
        state.error = action.payload as string;
      });
  },
});

// ============ 导出Actions ============

export const {
  resetConfig,
  clearError,
  resetUpdateStatus,
  updateLocalConfig,
  updateLocalNotificationSettings,
  updateLocalPrivacySettings,
} = configSlice.actions;

// ============ Selectors ============

export const selectConfig = (state: { config: ConfigState }) => state.config.config;
export const selectConfigLoading = (state: { config: ConfigState }) => state.config.isLoading;
export const selectConfigError = (state: { config: ConfigState }) => state.config.error;
export const selectUpdateStatus = (state: { config: ConfigState }) => state.config.updateStatus;
export const selectNotificationSettings = (state: { config: ConfigState }) =>
  state.config.config?.notification_settings;
export const selectPrivacySettings = (state: { config: ConfigState }) =>
  state.config.config?.privacy_settings;

// ============ 导出Reducer ============

export default configSlice.reducer;

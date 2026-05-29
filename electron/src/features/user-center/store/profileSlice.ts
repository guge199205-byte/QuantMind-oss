/**
 * 用户档案Redux Slice
 */

import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import { userCenterService } from '../services/userCenterService';
import type {
  UserProfile,
  UserProfileUpdate,
  LoadingState,
  AvatarUploadResponse,
} from '../types';

interface FetchProfileResult {
  profile: UserProfile;
  fetchedAt: string;
}

function syncLocalUserSnapshot(profile: UserProfile): void {
  try {
    const raw = localStorage.getItem('user');
    if (!raw) return;
    const parsed = JSON.parse(raw || '{}');
    const merged = {
      ...parsed,
      username: profile.username || parsed?.username || '',
      full_name: profile.username || parsed?.full_name || '',
      email: profile.email || parsed?.email || '',
    };
    localStorage.setItem('user', JSON.stringify(merged));
  } catch {
    // ignore snapshot sync errors
  }
}

// ============ 状态接口定义 ============

export interface ProfileState {
  profile: UserProfile | null;
  isLoading: boolean;
  error: string | null;
  updateStatus: LoadingState;
  avatarUploadStatus: LoadingState;
  avatarUploadProgress: number;
  lastFetchedAt: string | null;
}

// ============ 初始状态 ============

const initialState: ProfileState = {
  profile: null,
  isLoading: false,
  error: null,
  updateStatus: 'idle',
  avatarUploadStatus: 'idle',
  avatarUploadProgress: 0,
  lastFetchedAt: null,
};

// ============ 异步Thunk ============

/**
 * 获取用户档案
 */
export const fetchUserProfile = createAsyncThunk(
  'profile/fetchUserProfile',
  async (userId: string, { rejectWithValue }) => {
    try {
      const MAX_RETRIES = 3;
      let attempt = 0;
      let lastError: any = null;
      while (attempt < MAX_RETRIES) {
        try {
          const profile = await userCenterService.getUserProfile(userId);
          syncLocalUserSnapshot(profile);
          const fetchedAt = new Date().toISOString();
          const result: FetchProfileResult = {
            profile,
            fetchedAt,
          };
          return result;
        } catch (e: any) {
          lastError = e;
          await new Promise((r) => setTimeout(r, 300 * (attempt + 1)));
          attempt++;
        }
      }
      const msg = lastError?.message || 'Network Error: No response from server';
      return rejectWithValue({ message: msg });
    } catch (error: any) {
      return rejectWithValue({ message: error.message || 'Failed to fetch user profile' });
    }
  }
);

/**
 * 更新用户档案
 */
export const updateUserProfile = createAsyncThunk(
  'profile/updateUserProfile',
  async (
    { userId, data }: { userId: string; data: UserProfileUpdate },
    { rejectWithValue }
  ) => {
    try {
      const profile = await userCenterService.updateUserProfile(userId, data);
      syncLocalUserSnapshot(profile);
      return profile;
    } catch (error: any) {
      return rejectWithValue(error.message || 'Failed to update user profile');
    }
  }
);

/**
 * 上传头像
 */
export const uploadAvatar = createAsyncThunk(
  'profile/uploadAvatar',
  async (
    { userId, file }: { userId: string; file: File },
    { rejectWithValue, dispatch }
  ) => {
    try {
      const response = await userCenterService.uploadAvatar(userId, file, (percent) => {
        dispatch(profileSlice.actions.setAvatarUploadProgress(percent));
      });

      dispatch(profileSlice.actions.setAvatarUploadProgress(100));

      return response;
    } catch (error: any) {
      return rejectWithValue(error.message || 'Failed to upload avatar');
    }
  }
);

/**
 * 删除头像
 */
export const deleteAvatar = createAsyncThunk(
  'profile/deleteAvatar',
  async (
    { userId, fileKey }: { userId: string; fileKey: string },
    { rejectWithValue }
  ) => {
    try {
      await userCenterService.deleteAvatar(userId, fileKey);
      return { success: true };
    } catch (error: any) {
      return rejectWithValue(error.message || 'Failed to delete avatar');
    }
  }
);

// ============ Slice定义 ============

export const profileSlice = createSlice({
  name: 'profile',
  initialState,
  reducers: {
    /**
     * 重置状态
     */
    resetProfile: (state) => {
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
     * 设置头像上传进度
     */
    setAvatarUploadProgress: (state, action: PayloadAction<number>) => {
      state.avatarUploadProgress = action.payload;
    },

    /**
     * 更新本地档案数据（无需API调用）
     */
    updateLocalProfile: (state, action: PayloadAction<Partial<UserProfile>>) => {
      if (state.profile) {
        state.profile = {
          ...state.profile,
          ...action.payload,
          updated_at: new Date().toISOString(),
        };
      }
    },
  },
  extraReducers: (builder) => {
    // ===== 获取用户档案 =====
    builder
      .addCase(fetchUserProfile.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(fetchUserProfile.fulfilled, (state, action) => {
        state.isLoading = false;
        state.profile = action.payload.profile;
        state.lastFetchedAt = action.payload.fetchedAt;
        state.error = null;
      })
      .addCase(fetchUserProfile.rejected, (state, action) => {
        state.isLoading = false;
        const payload = action.payload as { message?: string } | string | undefined;
        state.error = (typeof payload === 'string' ? payload : payload?.message) || null;
      });

    // ===== 更新用户档案 =====
    builder
      .addCase(updateUserProfile.pending, (state) => {
        state.updateStatus = 'loading';
        state.error = null;
      })
      .addCase(updateUserProfile.fulfilled, (state, action) => {
        state.updateStatus = 'success';
        state.profile = action.payload;
        state.error = null;
      })
      .addCase(updateUserProfile.rejected, (state, action) => {
        state.updateStatus = 'error';
        state.error = action.payload as string;
      });

    // ===== 上传头像 =====
    builder
      .addCase(uploadAvatar.pending, (state) => {
        state.avatarUploadStatus = 'loading';
        state.avatarUploadProgress = 0;
        state.error = null;
      })
      .addCase(uploadAvatar.fulfilled, (state, action) => {
        state.avatarUploadStatus = 'success';
        state.avatarUploadProgress = 0;
        // 更新档案中的头像URL
        if (state.profile) {
          state.profile.avatar = action.payload.avatar_url;
        }
        state.error = null;
      })
      .addCase(uploadAvatar.rejected, (state, action) => {
        state.avatarUploadStatus = 'error';
        state.avatarUploadProgress = 0;
        state.error = action.payload as string;
      });

    // ===== 删除头像 =====
    builder
      .addCase(deleteAvatar.pending, (state) => {
        state.avatarUploadStatus = 'loading';
        state.error = null;
      })
      .addCase(deleteAvatar.fulfilled, (state) => {
        state.avatarUploadStatus = 'success';
        // 清除档案中的头像URL
        if (state.profile) {
          state.profile.avatar = undefined;
        }
        state.error = null;
      })
      .addCase(deleteAvatar.rejected, (state, action) => {
        state.avatarUploadStatus = 'error';
        state.error = action.payload as string;
      });
  },
});

// ============ 导出Actions ============

export const {
    resetProfile,
    clearError,
    resetUpdateStatus,
    setAvatarUploadProgress,
    updateLocalProfile,
  } = profileSlice.actions;

// ============ Selectors ============

export const selectProfile = (state: { profile: ProfileState }) => state.profile.profile;
export const selectProfileLoading = (state: { profile: ProfileState }) =>
  state.profile.isLoading;
export const selectProfileError = (state: { profile: ProfileState }) => state.profile.error;
export const selectUpdateStatus = (state: { profile: ProfileState }) =>
  state.profile.updateStatus;
export const selectAvatarUploadStatus = (state: { profile: ProfileState }) =>
  state.profile.avatarUploadStatus;
export const selectAvatarUploadProgress = (state: { profile: ProfileState }) =>
  state.profile.avatarUploadProgress;
export const selectProfileLastFetchedAt = (state: { profile: ProfileState }) =>
  state.profile.lastFetchedAt;

// ============ 导出Reducer ============

export default profileSlice.reducer;

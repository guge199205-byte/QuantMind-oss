/**
 * 用户中心自定义Hooks
 * 封装Redux store操作,简化组件中的使用
 */

import { useEffect } from 'react';
import { useAppDispatch, useAppSelector } from '../../../store';
import type { RootState } from '../../../store';
import {
  fetchUserProfile,
  updateUserProfile,
  uploadAvatar,
  deleteAvatar,
} from '../store/profileSlice';
import type { UserProfileUpdate } from '../types';

// ============ 用户档案Hooks ============

/**
 * 使用用户档案
 * @param userId 用户ID
 * @param autoFetch 是否自动获取
 */
export const useProfile = (userId: string, autoFetch = true) => {
  const dispatch = useAppDispatch();
  const profile = useAppSelector((state: RootState) => state.profile.profile);
  const isLoading = useAppSelector((state: RootState) => state.profile.isLoading);
  const error = useAppSelector((state: RootState) => state.profile.error);
  const updateStatus = useAppSelector((state: RootState) => state.profile.updateStatus);
  const avatarUploadStatus = useAppSelector((state: RootState) => state.profile.avatarUploadStatus);
  const avatarUploadProgress = useAppSelector((state: RootState) => state.profile.avatarUploadProgress);
  const lastFetchedAt = useAppSelector((state: RootState) => state.profile.lastFetchedAt);

  useEffect(() => {
    if (autoFetch && userId) {
      dispatch(fetchUserProfile(userId));
    }
  }, [dispatch, userId, autoFetch]);

  const handleUpdateProfile = async (data: UserProfileUpdate) => {
    return dispatch(updateUserProfile({ userId, data })).unwrap();
  };

  const handleUploadAvatar = async (file: File) => {
    return dispatch(uploadAvatar({ userId, file })).unwrap();
  };

  const handleDeleteAvatar = async (fileKey: string) => {
    return dispatch(deleteAvatar({ userId, fileKey })).unwrap();
  };

  const refetch = () => {
    dispatch(fetchUserProfile(userId));
  };

  return {
    profile,
    isLoading,
    error,
    updateStatus,
    avatarUploadStatus,
    avatarUploadProgress,
    updateProfile: handleUpdateProfile,
    uploadAvatar: handleUploadAvatar,
    deleteAvatar: handleDeleteAvatar,
    refetch,
    lastFetchedAt,
  };
};

/**
 * 使用头像上传功能
 */
export const useAvatarUpload = (userId: string) => {
  const dispatch = useAppDispatch();
  const uploadStatus = useAppSelector((state: RootState) => state.profile.avatarUploadStatus);
  const uploadProgress = useAppSelector((state: RootState) => state.profile.avatarUploadProgress);

  const handleUploadAvatar = async (file: File) => {
    return dispatch(uploadAvatar({ userId, file })).unwrap();
  };

  const handleDeleteAvatar = async (fileKey: string) => {
    return dispatch(deleteAvatar({ userId, fileKey })).unwrap();
  };

  return {
    uploadStatus,
    uploadProgress,
    uploadAvatar: handleUploadAvatar,
    deleteAvatar: handleDeleteAvatar,
  };
};

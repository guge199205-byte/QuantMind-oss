/**
 * Toast 通知状态管理
 * 
 * 用于管理临时 Toast 提示（成功/错误/警告/信息）
 * 与持久化业务通知（useNotifications）区分
 */

import { createSlice, PayloadAction } from '@reduxjs/toolkit';
import type { ToastNotification, ToastType } from '../../types/notification';

export interface ToastState {
  toasts: ToastNotification[];
}

const initialState: ToastState = {
  toasts: [],
};

const toastSlice = createSlice({
  name: 'toasts',
  initialState,
  reducers: {
    addToast: (state, action: PayloadAction<Omit<ToastNotification, 'id' | 'timestamp'>>) => {
      const toast: ToastNotification = {
        ...action.payload,
        id: Date.now().toString(),
        timestamp: Date.now(),
      };
      state.toasts.push(toast);
    },
    removeToast: (state, action: PayloadAction<string>) => {
      state.toasts = state.toasts.filter(t => t.id !== action.payload);
    },
    clearToasts: (state) => {
      state.toasts = [];
    },
  },
});

export const { addToast, removeToast, clearToasts } = toastSlice.actions;
export default toastSlice.reducer;

// 便捷方法
export const createToast = (
  type: ToastType,
  title: string,
  message: string,
  duration?: number
): Omit<ToastNotification, 'id' | 'timestamp'> => ({
  type,
  title,
  message,
  duration,
});

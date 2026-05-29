/**
 * 对话状态管理
 */

import { createSlice, PayloadAction } from '@reduxjs/toolkit';
import { Message } from '../types';

export interface ChatState {
  messages: Message[];
  isTyping: boolean;
  inputValue: string;
  isLoading: boolean;
}

const initialState: ChatState = {
  messages: [],
  isTyping: false,
  inputValue: '',
  isLoading: false,
};

const chatSlice = createSlice({
  name: 'quantbotChat',
  initialState,
  reducers: {
    addMessage: (state, action: PayloadAction<Message>) => {
      state.messages.push(action.payload);
    },
    updateMessage: (state, action: PayloadAction<{ id: string; updates: Partial<Message> }>) => {
      const index = state.messages.findIndex(m => m.id === action.payload.id);
      if (index !== -1) {
        state.messages[index] = { ...state.messages[index], ...action.payload.updates };
      }
    },
    setTyping: (state, action: PayloadAction<boolean>) => {
      state.isTyping = action.payload;
    },
    setInputValue: (state, action: PayloadAction<string>) => {
      state.inputValue = action.payload;
    },
    setLoading: (state, action: PayloadAction<boolean>) => {
      state.isLoading = action.payload;
    },
    clearMessages: (state) => {
      state.messages = [];
    },
    clearInput: (state) => {
      state.inputValue = '';
    },
  },
});

export const {
  addMessage,
  updateMessage,
  setTyping,
  setInputValue,
  setLoading,
  clearMessages,
  clearInput,
} = chatSlice.actions;

export default chatSlice.reducer;

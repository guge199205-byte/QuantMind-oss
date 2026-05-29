/**
 * 投资组合Redux Slice
 */

import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import { userCenterService } from '../services/userCenterService';
import type {
  UserPortfolio,
  PortfolioCreate,
  LoadingState,
} from '../types';

// ============ 状态接口定义 ============

export interface PortfoliosState {
  portfolios: UserPortfolio[];
  currentPortfolio: UserPortfolio | null;
  isLoading: boolean;
  error: string | null;
  createStatus: LoadingState;
  deleteStatus: LoadingState;
}

// ============ 初始状态 ============

const initialState: PortfoliosState = {
  portfolios: [],
  currentPortfolio: null,
  isLoading: false,
  error: null,
  createStatus: 'idle',
  deleteStatus: 'idle',
};

// ============ 异步Thunk ============

/**
 * 获取用户投资组合列表
 */
export const fetchUserPortfolios = createAsyncThunk(
  'portfolios/fetchUserPortfolios',
  async (userId: string, { rejectWithValue }) => {
    try {
      const portfolios = await userCenterService.getUserPortfolios(userId);
      return portfolios;
    } catch (error: any) {
      return rejectWithValue(error.message || 'Failed to fetch portfolios');
    }
  }
);

/**
 * 获取投资组合详情
 */
export const fetchPortfolioDetail = createAsyncThunk(
  'portfolios/fetchPortfolioDetail',
  async (portfolioId: number, { rejectWithValue }) => {
    try {
      const portfolio = await userCenterService.getPortfolioDetail(portfolioId);
      return portfolio;
    } catch (error: any) {
      return rejectWithValue(error.message || 'Failed to fetch portfolio detail');
    }
  }
);

/**
 * 创建投资组合
 */
export const createPortfolio = createAsyncThunk(
  'portfolios/createPortfolio',
  async (
    { userId, data }: { userId: string; data: PortfolioCreate },
    { rejectWithValue }
  ) => {
    try {
      const portfolio = await userCenterService.createPortfolio(userId, data);
      return portfolio;
    } catch (error: any) {
      return rejectWithValue(error.message || 'Failed to create portfolio');
    }
  }
);

// ============ Slice定义 ============

export const portfoliosSlice = createSlice({
  name: 'portfolios',
  initialState,
  reducers: {
    /**
     * 重置状态
     */
    resetPortfolios: (state) => {
      return initialState;
    },

    /**
     * 清除错误
     */
    clearError: (state) => {
      state.error = null;
    },

    /**
     * 设置当前组合
     */
    setCurrentPortfolio: (state, action: PayloadAction<UserPortfolio | null>) => {
      state.currentPortfolio = action.payload;
    },

    /**
     * 重置创建状态
     */
    resetCreateStatus: (state) => {
      state.createStatus = 'idle';
    },

    /**
     * 重置删除状态
     */
    resetDeleteStatus: (state) => {
      state.deleteStatus = 'idle';
    },

    /**
     * 更新本地组合数据
     */
    updateLocalPortfolio: (
      state,
      action: PayloadAction<{ id: number; data: Partial<UserPortfolio> }>
    ) => {
      const { id, data } = action.payload;
      const index = state.portfolios.findIndex((p) => p.id === id);
      if (index !== -1) {
        state.portfolios[index] = {
          ...state.portfolios[index],
          ...data,
          updated_at: new Date().toISOString(),
        };
      }
      if (state.currentPortfolio?.id === id) {
        state.currentPortfolio = {
          ...state.currentPortfolio,
          ...data,
          updated_at: new Date().toISOString(),
        };
      }
    },
  },
  extraReducers: (builder) => {
    // ===== 获取投资组合列表 =====
    builder
      .addCase(fetchUserPortfolios.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(fetchUserPortfolios.fulfilled, (state, action) => {
        state.isLoading = false;
        state.portfolios = action.payload;
        state.error = null;
      })
      .addCase(fetchUserPortfolios.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      });

    // ===== 获取投资组合详情 =====
    builder
      .addCase(fetchPortfolioDetail.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(fetchPortfolioDetail.fulfilled, (state, action) => {
        state.isLoading = false;
        state.currentPortfolio = action.payload;
        state.error = null;
      })
      .addCase(fetchPortfolioDetail.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      });

    // ===== 创建投资组合 =====
    builder
      .addCase(createPortfolio.pending, (state) => {
        state.createStatus = 'loading';
        state.error = null;
      })
      .addCase(createPortfolio.fulfilled, (state, action) => {
        state.createStatus = 'success';
        state.portfolios.unshift(action.payload);
        state.error = null;
      })
      .addCase(createPortfolio.rejected, (state, action) => {
        state.createStatus = 'error';
        state.error = action.payload as string;
      });
  },
});

// ============ 导出Actions ============

export const {
  resetPortfolios,
  clearError,
  setCurrentPortfolio,
  resetCreateStatus,
  resetDeleteStatus,
  updateLocalPortfolio,
} = portfoliosSlice.actions;

// ============ Selectors ============

export const selectPortfolios = (state: { portfolios: PortfoliosState }) =>
  state.portfolios.portfolios;
export const selectCurrentPortfolio = (state: { portfolios: PortfoliosState }) =>
  state.portfolios.currentPortfolio;
export const selectPortfoliosLoading = (state: { portfolios: PortfoliosState }) =>
  state.portfolios.isLoading;
export const selectPortfoliosError = (state: { portfolios: PortfoliosState }) =>
  state.portfolios.error;
export const selectCreateStatus = (state: { portfolios: PortfoliosState }) =>
  state.portfolios.createStatus;
export const selectDeleteStatus = (state: { portfolios: PortfoliosState }) =>
  state.portfolios.deleteStatus;

// ============ 导出Reducer ============

export default portfoliosSlice.reducer;

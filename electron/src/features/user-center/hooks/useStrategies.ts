/**
 * 策略管理Hooks
 */

import { useEffect, useCallback } from 'react';
import { useAppDispatch, useAppSelector } from '../../../store';
import type { RootState } from '../../../store';
import {
  fetchUserStrategies,
  fetchStrategyDetail,
  createStrategy,
  updateStrategy,
  deleteStrategy,
  enableStrategy,
  disableStrategy,
  setCurrentStrategy,
  updateFilters,
  clearFilters,
  setPage,
} from '../store/strategiesSlice';
import type { UserStrategy, StrategyUpdate, StrategyStatus } from '../types';

// ============ 策略列表Hook ============

/**
 * 使用策略列表
 * @param userId 用户ID
 * @param autoFetch 是否自动获取
 */
export const useStrategies = (userId: string, autoFetch = true) => {
  const dispatch = useAppDispatch();
  const strategies = useAppSelector((state: RootState) => state.strategies.strategies);
  const total = useAppSelector((state: RootState) => state.strategies.total);
  const page = useAppSelector((state: RootState) => state.strategies.page);
  const pageSize = useAppSelector((state: RootState) => state.strategies.pageSize);
  const isLoading = useAppSelector((state: RootState) => state.strategies.isLoading);
  const error = useAppSelector((state: RootState) => state.strategies.error);
  const filters = useAppSelector((state: RootState) => state.strategies.filters);

  // 自动获取数据
  useEffect(() => {
    if (autoFetch && userId) {
      dispatch(
        fetchUserStrategies({
          userId,
          page,
          pageSize,
          status: filters.status,
        })
      );
    }
  }, [dispatch, userId, page, pageSize, filters.status, autoFetch]);

  // 翻页
  const handlePageChange = useCallback(
    (newPage: number) => {
      dispatch(setPage(newPage));
    },
    [dispatch]
  );

  // 更新筛选条件
  const handleFilterChange = useCallback(
    (newFilters: { status?: StrategyStatus; search?: string }) => {
      dispatch(updateFilters(newFilters));
    },
    [dispatch]
  );

  // 清除筛选
  const handleClearFilters = useCallback(() => {
    dispatch(clearFilters());
  }, [dispatch]);

  // 刷新列表
  const refetch = useCallback(() => {
    dispatch(
      fetchUserStrategies({
        userId,
        page,
        pageSize,
        status: filters.status,
      })
    );
  }, [dispatch, userId, page, pageSize, filters.status]);

  return {
    strategies,
    total,
    page,
    pageSize,
    isLoading,
    error,
    filters,
    handlePageChange,
    handleFilterChange,
    handleClearFilters,
    refetch,
  };
};

// ============ 单个策略Hook ============

/**
 * 使用单个策略
 * @param userId 用户ID
 * @param strategyId 策略ID
 * @param autoFetch 是否自动获取
 */
export const useStrategy = (userId: string, strategyId?: string, autoFetch = true) => {
  const dispatch = useAppDispatch();
  const currentStrategy = useAppSelector((state: RootState) => state.strategies.currentStrategy);
  const isLoading = useAppSelector((state: RootState) => state.strategies.isLoading);
  const error = useAppSelector((state: RootState) => state.strategies.error);
  const updateStatus = useAppSelector((state: RootState) => state.strategies.updateStatus);

  useEffect(() => {
    if (autoFetch && userId && strategyId) {
      dispatch(fetchStrategyDetail({ userId, strategyId }));
    }
  }, [dispatch, userId, strategyId, autoFetch]);

  // 更新策略
  const handleUpdateStrategy = useCallback(
    async (data: StrategyUpdate) => {
      if (!strategyId) {
        throw new Error('Strategy ID is required');
      }
      return dispatch(updateStrategy({ userId, strategyId, data })).unwrap();
    },
    [dispatch, userId, strategyId]
  );

  // 启用策略
  const handleEnableStrategy = useCallback(async () => {
    if (!strategyId) {
      throw new Error('Strategy ID is required');
    }
    return dispatch(enableStrategy({ userId, strategyId })).unwrap();
  }, [dispatch, userId, strategyId]);

  // 禁用策略
  const handleDisableStrategy = useCallback(async () => {
    if (!strategyId) {
      throw new Error('Strategy ID is required');
    }
    return dispatch(disableStrategy({ userId, strategyId })).unwrap();
  }, [dispatch, userId, strategyId]);

  // 设置当前策略
  const setStrategy = useCallback(
    (strategy: UserStrategy | null) => {
      dispatch(setCurrentStrategy(strategy));
    },
    [dispatch]
  );

  return {
    strategy: currentStrategy,
    isLoading,
    error,
    updateStatus,
    updateStrategy: handleUpdateStrategy,
    enableStrategy: handleEnableStrategy,
    disableStrategy: handleDisableStrategy,
    setStrategy,
  };
};

// ============ 策略创建Hook ============

/**
 * 使用策略创建
 */
export const useCreateStrategy = (userId: string) => {
  const dispatch = useAppDispatch();
  const createStatus = useAppSelector((state: RootState) => state.strategies.createStatus);
  const error = useAppSelector((state: RootState) => state.strategies.error);

  const handleCreateStrategy = useCallback(
    async (data: Omit<UserStrategy, 'id' | 'created_at' | 'updated_at'>) => {
      return dispatch(createStrategy({ userId, data })).unwrap();
    },
    [dispatch, userId]
  );

  return {
    createStatus,
    error,
    createStrategy: handleCreateStrategy,
  };
};

// ============ 策略删除Hook ============

/**
 * 使用策略删除
 */
export const useDeleteStrategy = (userId: string) => {
  const dispatch = useAppDispatch();
  const deleteStatus = useAppSelector((state: RootState) => state.strategies.deleteStatus);
  const error = useAppSelector((state: RootState) => state.strategies.error);

  const handleDeleteStrategy = useCallback(
    async (strategyId: string) => {
      return dispatch(deleteStrategy({ userId, strategyId })).unwrap();
    },
    [dispatch, userId]
  );

  return {
    deleteStatus,
    error,
    deleteStrategy: handleDeleteStrategy,
  };
};

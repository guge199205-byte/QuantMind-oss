/**
 * 投资组合Hooks
 */

import { useEffect, useCallback } from 'react';
import { useAppDispatch, useAppSelector } from '../../../store';
import {
  fetchUserPortfolios,
  fetchPortfolioDetail,
  createPortfolio,
  setCurrentPortfolio,
} from '../store/portfoliosSlice';
import type { UserPortfolio, PortfolioCreate } from '../types';

// ============ 组合列表Hook ============

/**
 * 使用投资组合列表
 * @param userId 用户ID
 * @param autoFetch 是否自动获取
 */
export const usePortfolios = (userId: string, autoFetch = true) => {
  const dispatch = useAppDispatch();
  const portfolios = useAppSelector((state: any) => state.portfolios.portfolios);
  const isLoading = useAppSelector((state: any) => state.portfolios.isLoading);
  const error = useAppSelector((state: any) => state.portfolios.error);

  useEffect(() => {
    if (autoFetch && userId) {
      dispatch(fetchUserPortfolios(userId));
    }
  }, [dispatch, userId, autoFetch]);

  const refetch = useCallback(() => {
    dispatch(fetchUserPortfolios(userId));
  }, [dispatch, userId]);

  return {
    portfolios,
    isLoading,
    error,
    refetch,
  };
};

// ============ 单个组合Hook ============

/**
 * 使用单个投资组合
 * @param portfolioId 组合ID
 * @param autoFetch 是否自动获取
 */
export const usePortfolio = (portfolioId?: number, autoFetch = true) => {
  const dispatch = useAppDispatch();
  const currentPortfolio = useAppSelector((state: any) => state.portfolios.currentPortfolio);
  const isLoading = useAppSelector((state: any) => state.portfolios.isLoading);
  const error = useAppSelector((state: any) => state.portfolios.error);

  useEffect(() => {
    if (autoFetch && portfolioId) {
      dispatch(fetchPortfolioDetail(portfolioId));
    }
  }, [dispatch, portfolioId, autoFetch]);

  const setPortfolio = useCallback(
    (portfolio: UserPortfolio | null) => {
      dispatch(setCurrentPortfolio(portfolio));
    },
    [dispatch]
  );

  return {
    portfolio: currentPortfolio,
    isLoading,
    error,
    setPortfolio,
  };
};

// ============ 组合创建Hook ============

/**
 * 使用投资组合创建
 */
export const useCreatePortfolio = (userId: string) => {
  const dispatch = useAppDispatch();
  const createStatus = useAppSelector((state: any) => state.portfolios.createStatus);
  const error = useAppSelector((state: any) => state.portfolios.error);

  const handleCreatePortfolio = useCallback(
    async (data: PortfolioCreate) => {
      return dispatch(createPortfolio({ userId, data })).unwrap();
    },
    [dispatch, userId]
  );

  return {
    createStatus,
    error,
    createPortfolio: handleCreatePortfolio,
  };
};

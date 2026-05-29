/**
 * Redux相关hooks
 * 提供便捷的Redux状态访问和操作方法
 */

import { useDispatch, useSelector, TypedUseSelectorHook } from 'react-redux';

// 使用类型化的hooks
export const useAppDispatch = () => useDispatch<any>();
export const useAppSelector: TypedUseSelectorHook<any> = useSelector;

// 通用状态选择器hooks
export const useAuthState = () => useAppSelector(state => state.auth);
export const useUIState = () => useAppSelector(state => state.ui);
export const useToasts = () => useAppSelector(state => state.toasts);
export const useMarketData = () => useAppSelector(state => state.marketData);
export const useBacktestState = () => useAppSelector(state => state.backtest);
export const useAIStrategyState = () => useAppSelector(state => state.aiStrategy);

// 导出默认hooks以兼容性
export { useDispatch, useSelector };

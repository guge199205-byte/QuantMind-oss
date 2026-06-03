/**
 * 市场切换重置 Hook
 *
 * 当 currentMarket 变化时，重置各 feature store 的状态，
 * 避免跨市场数据污染。
 */

import { useEffect, useRef } from 'react';
import { useAppSelector, useAppDispatch } from '../store';
import { selectCurrentMarket, type AppMarket } from '../store/slices/uiSlice';
import { useBacktestCenterStore } from '../stores/backtestCenterStore';
import { useWizardV2Store } from '../features/strategy-wizard/store/wizardV2Store';
import { useMarketStore } from '../stores/market-store';

export function useMarketReset() {
  const currentMarket = useAppSelector(selectCurrentMarket);
  const prevMarketRef = useRef<AppMarket>(currentMarket);

  const resetBacktest = useBacktestCenterStore((s) => s.resetForMarket);
  const resetWizard = useWizardV2Store((s) => s.resetForMarket);
  const clearMarketCache = useMarketStore((s) => s.clearCache);

  useEffect(() => {
    if (prevMarketRef.current !== currentMarket) {
      prevMarketRef.current = currentMarket;

      // Reset all stores for the new market
      resetBacktest(currentMarket);
      resetWizard(currentMarket);
      clearMarketCache();
    }
  }, [currentMarket, resetBacktest, resetWizard, clearMarketCache]);
}

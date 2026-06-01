import React from 'react';
import { motion } from 'framer-motion';
import { useAppDispatch, useAppSelector } from '../../store';
import { setMarket, selectCurrentMarket, type AppMarket } from '../../store/slices/uiSlice';

interface MarketOption {
  id: AppMarket;
  label: string;
  color: string;
  bgColor: string;
  borderColor: string;
}

const MARKET_OPTIONS: MarketOption[] = [
  { id: 'CN', label: 'A股', color: 'text-red-600', bgColor: 'bg-red-50', borderColor: 'border-red-200' },
  { id: 'HK', label: '港股', color: 'text-orange-600', bgColor: 'bg-orange-50', borderColor: 'border-orange-200' },
  { id: 'US', label: '美股', color: 'text-blue-600', bgColor: 'bg-blue-50', borderColor: 'border-blue-200' },
  { id: 'CRYPTO', label: '区块链', color: 'text-purple-600', bgColor: 'bg-purple-50', borderColor: 'border-purple-200' },
];

export const MarketSelector: React.FC = () => {
  const dispatch = useAppDispatch();
  const currentMarket = useAppSelector(selectCurrentMarket);

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      className="flex items-center"
    >
      <div
        className="relative flex h-8 items-center rounded-full border border-slate-200/80 bg-white/68 backdrop-blur-md shadow-sm"
        role="radiogroup"
        aria-label="市场切换"
      >
        {MARKET_OPTIONS.map((market) => {
          const isActive = currentMarket === market.id;
          return (
            <button
              key={market.id}
              type="button"
              role="radio"
              aria-checked={isActive}
              onClick={() => dispatch(setMarket(market.id))}
              className={`relative z-10 flex items-center justify-center px-3 h-full text-[11px] font-bold tracking-tight transition-colors ${
                isActive ? 'text-slate-800' : 'text-slate-400 hover:text-slate-600'
              }`}
            >
              {isActive && (
                <motion.div
                  layoutId="market-active-bg"
                  className={`absolute inset-0.5 rounded-full ${market.bgColor} border ${market.borderColor} shadow-sm`}
                  transition={{ type: 'spring', bounce: 0.15, duration: 0.3 }}
                />
              )}
              <span className="relative z-10">{market.label}</span>
            </button>
          );
        })}
      </div>
    </motion.div>
  );
};

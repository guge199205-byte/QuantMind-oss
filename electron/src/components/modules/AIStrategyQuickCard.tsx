import React, { useState } from 'react';
import { useDispatch } from 'react-redux';
import { Brain, TrendingUp, Zap, ArrowRight } from 'lucide-react';
import { motion } from 'framer-motion';
import { setCurrentTab } from '../../store/slices/aiStrategySlice';

export const AIStrategyQuickCard: React.FC = () => {
  const [isHovered, setIsHovered] = useState(false);
  const dispatch = useDispatch();

  const handleGoToStrategy = () => {
    dispatch(setCurrentTab('strategy'));
  };

  const recentStrategies = [
    { name: '均线突破策略', performance: '+12.5%', status: 'active' },
    { name: '动量因子策略', performance: '+8.3%', status: 'testing' },
    { name: '套利策略', performance: '+15.2%', status: 'active' }
  ];

  return (
    <motion.div
      className="bg-white rounded-lg border border-gray-200 p-6 h-full relative overflow-hidden"
      onHoverStart={() => setIsHovered(true)}
      onHoverEnd={() => setIsHovered(false)}
      whileHover={{ scale: 1.02 }}
      transition={{ duration: 0.2 }}
    >
      {/* 背景装饰 */}
      <div className="absolute top-0 right-0 w-24 h-24 bg-gradient-to-bl from-blue-50 to-transparent rounded-bl-full opacity-50" />

      {/* 头部 */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center space-x-3">
          <div className="relative">
            <Brain className="w-8 h-8 text-[var(--primary-blue-light)]" />
            <motion.div
              className="absolute -top-1 -right-1 w-3 h-3 bg-[var(--success)] rounded-full"
              animate={{ scale: isHovered ? 1.2 : 1 }}
              transition={{ duration: 0.2 }}
            />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-[var(--text-primary)]">AI策略生成</h3>
            <p className="text-sm text-[var(--text-secondary)]">智能策略助手</p>
          </div>
        </div>
        <motion.button
          onClick={handleGoToStrategy}
          className="p-2 hover:bg-[var(--info-bg)] rounded-lg transition-colors"
          whileHover={{ scale: 1.1 }}
          whileTap={{ scale: 0.95 }}
        >
          <ArrowRight className="w-5 h-5 text-[var(--primary-blue-light)]" />
        </motion.button>
      </div>

      {/* 快速统计 */}
      <div className="grid grid-cols-2 gap-3 mb-4">
        <div className="bg-[var(--info-bg)] rounded-lg p-3">
          <div className="flex items-center space-x-2">
            <TrendingUp className="w-4 h-4 text-[var(--info)]" />
            <span className="text-sm font-medium text-[var(--info-dark)]">活跃策略</span>
          </div>
          <p className="text-xl font-bold text-[var(--info-dark)] mt-1">5</p>
        </div>
        <div className="bg-[var(--success-bg)] rounded-lg p-3">
          <div className="flex items-center space-x-2">
            <Zap className="w-4 h-4 text-[var(--success)]" />
            <span className="text-sm font-medium text-[var(--success-dark)]">总收益</span>
          </div>
          <p className="text-xl font-bold text-[var(--profit-primary)] mt-1">+23.7%</p>
        </div>
      </div>

      {/* 最近策略列表 */}
      <div className="space-y-2">
        <h4 className="text-sm font-medium text-[var(--text-secondary)] mb-2">最近策略</h4>
        {recentStrategies.map((strategy, index) => (
          <motion.div
            key={index}
            className="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-[var(--bg-secondary)] transition-colors cursor-pointer"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.1 }}
          >
            <div className="flex-1">
              <p className="text-sm font-medium text-[var(--text-primary)]">{strategy.name}</p>
              <div className="flex items-center space-x-2 mt-1">
                <span className={`inline-block w-2 h-2 rounded-full ${
                  strategy.status === 'active' ? 'bg-[var(--strategy-running)]' : 'bg-[var(--strategy-testing)]'
                }`} />
                <span className="text-xs text-[var(--text-tertiary)]">
                  {strategy.status === 'active' ? '运行中' : '测试中'}
                </span>
              </div>
            </div>
            <div className="text-right">
              <p className={`text-sm font-semibold ${
                strategy.performance.startsWith('+') ? 'text-[var(--profit-primary)]' : 'text-[var(--loss-primary)]'
              }`}>
                {strategy.performance}
              </p>
            </div>
          </motion.div>
        ))}
      </div>

      {/* 快速操作按钮 */}
      <motion.button
        onClick={handleGoToStrategy}
        className="w-full mt-4 py-2 px-4 bg-[var(--primary-blue-light)] text-white rounded-lg font-medium text-sm hover:bg-[var(--primary-blue)] transition-colors"
        whileHover={{ scale: 1.02 }}
        whileTap={{ scale: 0.98 }}
      >
        生成新策略
      </motion.button>
    </motion.div>
  );
};

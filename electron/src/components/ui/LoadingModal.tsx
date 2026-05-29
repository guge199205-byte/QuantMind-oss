import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Loader2, Clock, Brain, Zap } from 'lucide-react';

interface LoadingModalProps {
  isOpen: boolean;
  title?: string;
  message?: string;
  showAnimation?: boolean;
}

export const LoadingModal: React.FC<LoadingModalProps> = ({
  isOpen,
  title = '正在生成策略',
  message = '正在根据您的需求生成策略，请稍候，处理时间将根据策略复杂度决定',
  showAnimation = true
}) => {
  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
        >
          <motion.div
            initial={{ scale: 0.9, opacity: 0, y: 20 }}
            animate={{ scale: 1, opacity: 1, y: 0 }}
            exit={{ scale: 0.9, opacity: 0, y: 20 }}
            transition={{ type: 'spring', damping: 25, stiffness: 300 }}
            className="bg-white rounded-2xl shadow-2xl p-8 max-w-md mx-4 border border-gray-100"
          >
            {/* 加载动画区域 */}
            <div className="flex flex-col items-center space-y-6">
              {/* 动画图标 */}
              <div className="relative">
                {showAnimation && (
                  <motion.div
                    animate={{ rotate: 360 }}
                    transition={{ duration: 2, repeat: Infinity, ease: 'linear' }}
                    className="absolute inset-0"
                  >
                    <Zap className="w-12 h-12 text-blue-500/20" />
                  </motion.div>
                )}
                <motion.div
                  animate={{ scale: [1, 1.1, 1] }}
                  transition={{ duration: 2, repeat: Infinity }}
                >
                  <Brain className="w-12 h-12 text-blue-600" />
                </motion.div>
              </div>

              {/* 旋转加载器 */}
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
              >
                <Loader2 className="w-8 h-8 text-blue-600" />
              </motion.div>

              {/* 内容区域 */}
              <div className="text-center space-y-3">
                <h3 className="text-xl font-semibold text-gray-900">{title}</h3>

                <div className="flex items-center justify-center space-x-2 text-gray-600">
                  <Clock className="w-4 h-4" />
                  <p className="text-sm">{message}</p>
                </div>

                {/* 进度指示器 */}
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <motion.div
                    initial={{ width: '0%' }}
                    animate={{ width: '100%' }}
                    transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
                    className="bg-gradient-to-r from-blue-500 to-purple-600 h-2 rounded-full"
                  />
                </div>

                {/* 提示信息 */}
                <div className="text-xs text-gray-500 space-y-1">
                  <p>• AI正在分析您的策略需求</p>
                  <p>• 生成完整的交易逻辑和代码</p>
                  <p>• 优化风险控制参数</p>
                  <p>• 这个过程可能需要几十秒时间</p>
                </div>
              </div>
            </div>

            {/* 底部装饰 */}
            <div className="mt-6 flex justify-center space-x-2">
              {[1, 2, 3].map((i) => (
                <motion.div
                  key={i}
                  animate={{ scale: [1, 1.5, 1] }}
                  transition={{ duration: 1, delay: i * 0.2, repeat: Infinity }}
                  className="w-2 h-2 bg-blue-400 rounded-full"
                />
              ))}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

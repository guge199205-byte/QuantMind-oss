/**
 * 参数优化模块（适配新布局）
 */

import React from 'react';
import { motion } from 'framer-motion';
import { ParameterOptimization } from '../optimization';

export const ParameterOptimizationModule: React.FC = () => {
  return (
    <div className="h-full p-6">
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.25 }}
        className="bg-white rounded-2xl border border-gray-200 shadow-sm p-4 h-full overflow-hidden"
      >
        <ParameterOptimization />
      </motion.div>
    </div>
  );
};

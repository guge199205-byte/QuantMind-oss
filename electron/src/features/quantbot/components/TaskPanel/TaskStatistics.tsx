/**
 * 任务统计面板组件
 */

import React from 'react';
import { useSelector } from 'react-redux';
import { motion } from 'framer-motion';
import { Activity, CheckCircle, TrendingUp } from 'lucide-react';
import { RootState } from '../../../../store';

const TaskStatistics: React.FC = () => {
  const statistics = useSelector(
    (state: RootState) => state.quantbotTask?.statistics || {
      total: 0,
      active: 0,
      completed: 0,
      failed: 0,
      successRate: 0,
    }
  );

  const stats = [
    {
      label: '进行中',
      value: statistics.active,
      icon: Activity,
      color: 'text-blue-600',
      bgColor: 'bg-blue-50',
    },
    {
      label: '已完成',
      value: statistics.completed,
      icon: CheckCircle,
      color: 'text-green-600',
      bgColor: 'bg-green-50',
    },
    {
      label: '成功率',
      value: `${statistics.successRate}%`,
      icon: TrendingUp,
      color: 'text-purple-600',
      bgColor: 'bg-purple-50',
    },
  ];

  return (
    <div>
      <h3 className="text-sm font-semibold text-gray-700 mb-3">任务统计</h3>

      <div className="grid grid-cols-3 gap-2">
        {stats.map((stat, index) => (
          <motion.div
            key={index}
            initial={{ scale: 0.9, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ delay: index * 0.1 }}
            className={`${stat.bgColor} rounded-lg p-3 text-center`}
          >
            <stat.icon className={`w-4 h-4 ${stat.color} mx-auto mb-1`} />
            <div className={`text-lg font-bold ${stat.color}`}>
              {stat.value}
            </div>
            <div className="text-xs text-gray-600 mt-1">{stat.label}</div>
          </motion.div>
        ))}
      </div>
    </div>
  );
};

export default TaskStatistics;

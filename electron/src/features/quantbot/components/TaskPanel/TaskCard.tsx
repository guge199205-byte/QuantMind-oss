/**
 * 任务卡片组件
 */

import React from 'react';
import { motion } from 'framer-motion';
import { useDispatch } from 'react-redux';
import {
  BarChart3,
  TrendingUp,
  Search,
  LineChart,
  Loader2,
  CheckCircle2,
  XCircle,
  AlertCircle
} from 'lucide-react';
import { ActiveTask } from '../../types';
import { removeTask, moveToHistory } from '../../store/taskSlice';

interface TaskCardProps {
  task: ActiveTask;
}

const iconMap = {
  financial_report: BarChart3,
  stock_query: LineChart,
  stock_selection: Search,
  strategy_advice: BarChart3,
  strategy_analysis: BarChart3,
  trade_execution: TrendingUp,
  software_info: LineChart,
  general_chat: LineChart,
  deep_analysis: BarChart3,
};

const statusConfig = {
  pending: { icon: AlertCircle, color: 'text-yellow-500', bgColor: 'bg-yellow-50' },
  running: { icon: Loader2, color: 'text-blue-500', bgColor: 'bg-blue-50', spin: true },
  completed: { icon: CheckCircle2, color: 'text-green-500', bgColor: 'bg-green-50' },
  failed: { icon: XCircle, color: 'text-red-500', bgColor: 'bg-red-50' },
  cancelled: { icon: XCircle, color: 'text-gray-500', bgColor: 'bg-gray-50' },
};

const TaskCard: React.FC<TaskCardProps> = ({ task }) => {
  const dispatch = useDispatch();
  const TaskIcon = iconMap[task.type] || BarChart3;
  const statusInfo = statusConfig[task.status] || statusConfig.pending;
  const StatusIcon = statusInfo.icon;

  const handleCancel = () => {
    dispatch(removeTask(task.id));
  };

  const handleComplete = () => {
    dispatch(moveToHistory({ taskId: task.id }));
  };

  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -20 }}
      className="bg-white border border-gray-200 rounded-lg p-3 shadow-sm hover:shadow-md transition-shadow"
    >
      {/* 任务头部 */}
      <div className="flex items-start gap-2 mb-2">
        <div className={`p-2 rounded-lg ${statusInfo.bgColor}`}>
          <TaskIcon className={`w-4 h-4 ${statusInfo.color}`} />
        </div>

        <div className="flex-1 min-w-0">
          <h4 className="text-sm font-medium text-gray-800 truncate">
            {task.title}
          </h4>
          <p className="text-xs text-gray-500 line-clamp-2">
            {task.description}
          </p>
        </div>

        <div className={`p-1 rounded ${statusInfo.bgColor}`}>
          <StatusIcon
            className={`w-4 h-4 ${statusInfo.color} ${(statusInfo as any).spin ? 'animate-spin' : ''}`}
          />
        </div>
      </div>

      {/* 进度条 */}
      {task.progress !== undefined && (
        <div className="mb-2">
          <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${task.progress}%` }}
              className="h-full bg-gradient-to-r from-blue-500 to-purple-600"
            />
          </div>
          <div className="text-xs text-gray-500 mt-1 text-right">
            {task.progress}%
          </div>
        </div>
      )}

      {/* 监控数据 */}
      {task.monitorData && (
        <div className="mb-2 p-2 bg-gray-50 rounded text-xs space-y-1">
          <div className="flex justify-between">
            <span className="text-gray-600">当前价:</span>
            <span className="font-medium">¥{task.monitorData.currentPrice.toFixed(2)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-600">目标价:</span>
            <span className="font-medium">¥{task.monitorData.targetPrice.toFixed(2)}</span>
          </div>
          <div className="text-gray-500 text-center pt-1 border-t border-gray-200">
            已检查 {task.monitorData.checkCount} 次
          </div>
        </div>
      )}

      {/* 操作按钮 */}
      {task.actions && task.actions.length > 0 && (
        <div className="flex gap-2 mt-2">
          {task.actions.map((action, index) => (
            <button
              key={index}
              onClick={action.onClick}
              className={`flex-1 px-3 py-1.5 rounded text-xs font-medium transition-colors ${
                action.variant === 'danger'
                  ? 'bg-red-50 text-red-600 hover:bg-red-100'
                  : action.variant === 'primary'
                  ? 'bg-blue-50 text-blue-600 hover:bg-blue-100'
                  : 'bg-gray-50 text-gray-600 hover:bg-gray-100'
              }`}
            >
              {action.label}
            </button>
          ))}
        </div>
      )}

      {/* 默认操作按钮 */}
      {(!task.actions || task.actions.length === 0) && task.status === 'running' && (
        <button
          onClick={handleCancel}
          className="w-full mt-2 px-3 py-1.5 bg-red-50 text-red-600 rounded text-xs font-medium hover:bg-red-100 transition-colors"
        >
          取消任务
        </button>
      )}
    </motion.div>
  );
};

export default TaskCard;

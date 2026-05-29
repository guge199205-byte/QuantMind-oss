/**
 * 历史任务列表组件
 */

import React, { useState } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { motion, AnimatePresence } from 'framer-motion';
import { History, CheckCircle2, XCircle, Trash2 } from 'lucide-react';
import { RootState } from '../../../../store';
import { clearHistory } from '../../store/taskSlice';

const HistoryTasks: React.FC = () => {
  const dispatch = useDispatch();
  const historyTasks = useSelector(
    (state: RootState) => state.quantbotTask?.history || []
  );
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);

  const selectedTask = historyTasks.find(task => task.id === selectedTaskId) || null;

  const handleClearAll = () => {
    if (window.confirm('确定要清空所有历史记录吗？')) {
      dispatch(clearHistory());
    }
  };

  const formatRelativeTime = (date: string) => {
    const now = new Date();
    const diff = now.getTime() - new Date(date).getTime();
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);

    if (minutes < 1) return '刚刚';
    if (minutes < 60) return `${minutes}分钟前`;
    if (hours < 24) return `${hours}小时前`;
    return `${days}天前`;
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-gray-700 flex items-center gap-2">
          <History className="w-4 h-4" />
          历史记录 ({historyTasks.length})
        </h3>

        {historyTasks.length > 0 && (
          <button
            onClick={handleClearAll}
            className="text-xs text-gray-500 hover:text-red-600 transition-colors flex items-center gap-1"
          >
            <Trash2 className="w-3 h-3" />
            清空
          </button>
        )}
      </div>

      {historyTasks.length === 0 ? (
        <div className="text-center py-4 text-gray-400">
          <div className="text-2xl mb-1">📝</div>
          <div className="text-xs">暂无历史记录</div>
        </div>
      ) : (
        <div className="space-y-2 max-h-60 overflow-y-auto">
          <AnimatePresence>
            {historyTasks.map((task) => (
              <motion.div
                key={task.id}
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="bg-gray-50 rounded-lg p-2 text-xs"
              >
                <div className="flex items-start gap-2">
                  {task.status === 'completed' ? (
                    <CheckCircle2 className="w-4 h-4 text-green-500 flex-shrink-0 mt-0.5" />
                  ) : (
                    <XCircle className="w-4 h-4 text-red-500 flex-shrink-0 mt-0.5" />
                  )}

                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-gray-700 truncate">
                      {task.title}
                    </div>
                    <div className="text-gray-500 mt-0.5">
                      {formatRelativeTime(task.completedAt)}
                    </div>

                    {task.result && (
                      <div className="text-gray-600 mt-1 line-clamp-2">
                        {task.result}
                      </div>
                    )}
                  </div>
                </div>

                {/* 操作按钮 */}
                {(task.canView || task.canRetry) && (
                  <div className="flex gap-2 mt-2">
                    {task.canView && (
                      <button
                        onClick={() => setSelectedTaskId(task.id)}
                        className="flex-1 px-2 py-1 bg-white text-gray-600 rounded hover:bg-gray-100 transition-colors"
                      >
                        查看
                      </button>
                    )}
                    {task.canRetry && (
                      <button className="flex-1 px-2 py-1 bg-white text-blue-600 rounded hover:bg-blue-50 transition-colors">
                        重试
                      </button>
                    )}
                  </div>
                )}
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      )}

      <HistoryDetailModal
        open={!!selectedTask}
        onClose={() => setSelectedTaskId(null)}
        title={selectedTask?.title}
        status={selectedTask?.status}
        completedAt={selectedTask?.completedAt}
        result={selectedTask?.result}
      />
    </div>
  );
};

export default HistoryTasks;

export const HistoryDetailModal: React.FC<{
  open: boolean;
  onClose: () => void;
  title?: string;
  status?: 'completed' | 'failed';
  completedAt?: string;
  result?: string;
}> = ({ open, onClose, title, status, completedAt, result }) => {
  if (!open) return null;

  const statusText = status === 'completed' ? '成功' : '失败';
  const statusColor = status === 'completed' ? 'text-green-600' : 'text-red-600';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4">
      <div className="w-full max-w-xl rounded-2xl bg-white shadow-xl border border-gray-200">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200">
          <div>
            <div className="text-sm text-gray-500">历史详情</div>
            <div className="text-base font-semibold text-gray-800 truncate">{title}</div>
          </div>
          <button
            onClick={onClose}
            className="px-2 py-1 text-sm text-gray-500 hover:text-gray-700"
          >
            关闭
          </button>
        </div>

        <div className="px-5 py-4 space-y-3">
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-500">状态</span>
            <span className={`font-medium ${statusColor}`}>{statusText}</span>
          </div>
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-500">时间</span>
            <span className="text-gray-700">
              {completedAt ? new Date(completedAt).toLocaleString('zh-CN') : '-'}
            </span>
          </div>
          <div className="text-sm text-gray-500">结果</div>
          <div className="text-sm text-gray-800 whitespace-pre-wrap bg-gray-50 border border-gray-200 rounded-lg p-3 max-h-64 overflow-y-auto">
            {result || '无结果'}
          </div>
        </div>
      </div>
    </div>
  );
};

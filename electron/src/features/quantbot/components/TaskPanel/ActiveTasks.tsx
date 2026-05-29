/**
 * 正在执行的任务列表组件
 */

import React from 'react';
import { useSelector } from 'react-redux';
import { motion, AnimatePresence } from 'framer-motion';
import { Loader2 } from 'lucide-react';
import { RootState } from '../../../../store';
import TaskCard from './TaskCard';

const ActiveTasks: React.FC = () => {
  const activeTasks = useSelector(
    (state: RootState) => state.quantbotTask?.active || []
  );

  return (
    <div>
      <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
        <Loader2 className="w-4 h-4 animate-spin" />
        正在执行 ({activeTasks.length})
      </h3>

      {activeTasks.length === 0 ? (
        <div className="text-center py-8 text-gray-400">
          <div className="text-3xl mb-2">📭</div>
          <div className="text-sm">暂无进行中的任务</div>
        </div>
      ) : (
        <div className="space-y-3">
          <AnimatePresence>
            {activeTasks.map((task) => (
              <TaskCard key={task.id} task={task} />
            ))}
          </AnimatePresence>
        </div>
      )}
    </div>
  );
};

export default ActiveTasks;

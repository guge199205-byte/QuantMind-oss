/**
 * 任务轮询 Hook
 * 自动获取和更新任务状态
 */

import { useEffect, useCallback, useRef } from 'react';
import { useDispatch } from 'react-redux';
import { updateTask, moveToHistory } from '../store/taskSlice';
import agentApi from '../services/agentApi';
import { ActiveTask, TaskType } from '../types';

export const useTaskPolling = (enabled: boolean = true, interval: number = 3000) => {
  const dispatch = useDispatch();
  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  const lastFetchRef = useRef<number>(0);

  const fetchTasks = useCallback(async () => {
    try {
      const tasks = await agentApi.getActiveTasks();

      tasks.forEach(task => {
        // 将后端任务转换为前端格式
        const mappedStatus = mapTaskStatus(task.status);
        const activeTask: Partial<ActiveTask> = {
          id: task.task_id,
          type: mapTaskType(task.type),
          title: task.title,
          description: task.description,
          status: mappedStatus,
          progress: task.progress || 0,
          createdAt: String(task.created_at || new Date().toISOString()),
          estimatedTime: undefined, // 可以从metadata中获取
        };

        // 如果任务已完成或失败，移到历史记录
        if (mappedStatus === 'completed' || mappedStatus === 'failed') {
          dispatch(moveToHistory({
            taskId: task.task_id,
            result: task.result ? JSON.stringify(task.result) : task.error,
          }));
        } else {
          // 更新现有任务或添加新任务
          dispatch(updateTask({
            id: task.task_id,
            updates: activeTask,
          }));
        }
      });

      lastFetchRef.current = Date.now();
    } catch (error) {
      console.error('Failed to fetch tasks:', error);
    }
  }, [dispatch]);

  useEffect(() => {
    if (!enabled) {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      return;
    }

    // 立即执行一次
    fetchTasks();

    // 设置轮询
    intervalRef.current = setInterval(fetchTasks, interval);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [enabled, interval, fetchTasks]);

  return {
    fetchTasks,
    lastFetch: lastFetchRef.current,
  };
};

// 映射任务类型
function mapTaskType(backendType: string): TaskType {
  return backendType as TaskType;
}

// 映射任务状态
function mapTaskStatus(backendStatus: string) {
  const statusMap: Record<string, any> = {
    'pending': 'pending',
    'running': 'running',
    'completed': 'completed',
    'failed': 'failed',
    'cancelled': 'cancelled',
  };
  return statusMap[backendStatus] || 'pending';
}

export default useTaskPolling;

import { useEffect, useRef } from 'react';
import type { TaskInfo } from '../types/analysis';
import { useTaskStream } from './useTaskStream';

type UseDashboardLifecycleOptions = {
  loadInitialHistory: () => Promise<void>;
  refreshHistory: (silent?: boolean) => Promise<void>;
  refreshActiveTasks: () => Promise<void>;
  syncTaskCreated: (task: TaskInfo) => void;
  syncTaskUpdated: (task: TaskInfo) => void;
  syncTaskFailed: (task: TaskInfo) => void;
  removeTask: (taskId: string) => void;
  enabled?: boolean;
};

export function useDashboardLifecycle({
  loadInitialHistory,
  refreshHistory,
  refreshActiveTasks,
  syncTaskCreated,
  syncTaskUpdated,
  syncTaskFailed,
  removeTask,
  enabled = true,
}: UseDashboardLifecycleOptions): void {
  const removalTimeoutsRef = useRef<number[]>([]);

  useEffect(() => {
    if (!enabled) {
      return;
    }

    void loadInitialHistory();
    void refreshActiveTasks();
  }, [enabled, loadInitialHistory, refreshActiveTasks]);

  useEffect(() => {
    if (!enabled) {
      return;
    }

    const intervalId = window.setInterval(() => {
      void refreshHistory(true);
      void refreshActiveTasks();
    }, 30_000);

    return () => window.clearInterval(intervalId);
  }, [enabled, refreshHistory, refreshActiveTasks]);

  useEffect(() => {
    if (!enabled) {
      return;
    }

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        void refreshHistory(true);
        void refreshActiveTasks();
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
  }, [enabled, refreshHistory, refreshActiveTasks]);

  useEffect(() => {
    return () => {
      removalTimeoutsRef.current.forEach((timeoutId) => window.clearTimeout(timeoutId));
      removalTimeoutsRef.current = [];
    };
  }, []);

  const scheduleTaskRemoval = (taskId: string, delayMs: number) => {
    const timeoutId = window.setTimeout(() => {
      removeTask(taskId);
      removalTimeoutsRef.current = removalTimeoutsRef.current.filter((item) => item !== timeoutId);
    }, delayMs);

    removalTimeoutsRef.current.push(timeoutId);
  };

  useTaskStream({
    onTaskCreated: syncTaskCreated,
    onTaskStarted: syncTaskUpdated,
    onTaskProgress: syncTaskUpdated,
    onConnected: () => {
      void refreshActiveTasks();
    },
    onTaskCompleted: (task) => {
      syncTaskUpdated(task);
      void refreshHistory(true);
      scheduleTaskRemoval(task.taskId, 2_000);
    },
    onTaskFailed: (task) => {
      syncTaskFailed(task);
      scheduleTaskRemoval(task.taskId, 5_000);
    },
    onError: () => {
      console.warn('SSE connection disconnected, reconnecting...');
    },
    enabled,
  });
}

export default useDashboardLifecycle;

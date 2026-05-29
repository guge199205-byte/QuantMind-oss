/**
 * 任务状态管理
 */

import { createSlice, PayloadAction } from '@reduxjs/toolkit';
import { ActiveTask, HistoryTask, TaskStatistics } from '../types';

export interface TaskState {
  active: ActiveTask[];
  history: HistoryTask[];
  statistics: TaskStatistics;
}

const initialState: TaskState = {
  active: [],
  history: [],
  statistics: {
    total: 0,
    active: 0,
    completed: 0,
    failed: 0,
    successRate: 0,
  },
};

const taskSlice = createSlice({
  name: 'quantbotTask',
  initialState,
  reducers: {
    addTask: (state, action: PayloadAction<ActiveTask>) => {
      state.active.push(action.payload);
      state.statistics.active = state.active.length;
      state.statistics.total++;
    },
    updateTask: (state, action: PayloadAction<{ id: string; updates: Partial<ActiveTask> }>) => {
      const index = state.active.findIndex(t => t.id === action.payload.id);
      if (index !== -1) {
        state.active[index] = { ...state.active[index], ...action.payload.updates };
      }
    },
    removeTask: (state, action: PayloadAction<string>) => {
      state.active = state.active.filter(t => t.id !== action.payload);
      state.statistics.active = state.active.length;
    },
    moveToHistory: (state, action: PayloadAction<{ taskId: string; result?: string }>) => {
      const task = state.active.find(t => t.id === action.payload.taskId);
      if (task) {
        if (state.history.some(h => h.id === task.id)) {
          state.active = state.active.filter(t => t.id !== action.payload.taskId);
          return;
        }
        const historyTask: HistoryTask = {
          id: task.id,
          type: task.type,
          title: task.title,
          status: task.status === 'completed' ? 'completed' : 'failed',
          completedAt: new Date().toISOString(),
          result: action.payload.result,
          canRetry: task.status === 'failed',
          canView: true,
        };
        state.history.unshift(historyTask);
        state.active = state.active.filter(t => t.id !== action.payload.taskId);

        if (historyTask.status === 'completed') {
          state.statistics.completed++;
        } else {
          state.statistics.failed++;
        }
        state.statistics.active = state.active.length;
        state.statistics.successRate =
          state.statistics.total > 0
            ? Math.round((state.statistics.completed / state.statistics.total) * 100)
            : 0;
      }
    },
    addHistoryEntry: (state, action: PayloadAction<HistoryTask>) => {
      const incoming = action.payload;
      const incomingTime = new Date(incoming.completedAt).getTime();
      const isDuplicate = state.history.some(h => {
        const timeDiff = Math.abs(new Date(h.completedAt).getTime() - incomingTime);
        return (
          h.title === incoming.title &&
          h.status === incoming.status &&
          h.result === incoming.result &&
          timeDiff < 60000
        );
      });
      if (isDuplicate) {
        return;
      }
      state.history.unshift(action.payload);
    },
    clearHistory: (state) => {
      state.history = [];
    },
    updateStatistics: (state) => {
      state.statistics.active = state.active.length;
      state.statistics.successRate =
        state.statistics.total > 0
          ? Math.round((state.statistics.completed / state.statistics.total) * 100)
          : 0;
    },
  },
});

export const {
  addTask,
  updateTask,
  removeTask,
  moveToHistory,
  addHistoryEntry,
  clearHistory,
  updateStatistics,
} = taskSlice.actions;

export default taskSlice.reducer;

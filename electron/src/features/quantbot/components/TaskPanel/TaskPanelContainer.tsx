/**
 * 任务面板容器组件
 */

import React from 'react';
import SessionHeader from './SessionHeader';
import SessionList from './SessionList';
import { useSessionStore } from '../../store/sessionStore';

const TaskPanelContainer: React.FC = () => {
  const { createSession, loading } = useSessionStore();

  const handleNewChat = async () => {
    try {
      await createSession();
    } catch (error) {
      console.error('Create session failed:', error);
    }
  };

  return (
    <div className="flex flex-col h-full">
      <SessionHeader onNewChat={handleNewChat} loading={loading} />

      <div className="px-4 py-3 text-xs text-gray-500 border-b border-gray-100 bg-gray-50/60">
        当前右侧面板用于管理会话列表；任务系统将在后续能力恢复后单独接入。
      </div>

      <SessionList />

    </div>
  );
};

export default TaskPanelContainer;

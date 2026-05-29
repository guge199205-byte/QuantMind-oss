/**
 * 对话容器组件
 */

import React from 'react';
import MessageList from './MessageList';
import ChatInput from './ChatInput';

const ChatContainer: React.FC = () => {
  return (
    <div className="flex-1 flex flex-col bg-white overflow-hidden">
      {/* 消息列表区域 */}
      <MessageList />

      {/* 输入区域 */}
      <div className="flex-shrink-0 border-t border-gray-200 px-4 pt-4 pb-[60px]">
        <ChatInput />
      </div>
    </div>
  );
};

export default ChatContainer;

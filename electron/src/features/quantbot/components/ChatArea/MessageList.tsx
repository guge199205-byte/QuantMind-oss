/**
 * 消息列表组件
 */

import React, { useEffect, useRef } from 'react';
import { useSelector } from 'react-redux';
import { motion, AnimatePresence } from 'framer-motion';
import MessageItem from './MessageItem';
import { RootState } from '../../../../store';

const MessageList: React.FC = () => {
  const messages = useSelector((state: RootState) => state.quantbotChat?.messages || []);
  const isTyping = useSelector((state: RootState) => state.quantbotChat?.isTyping || false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const prevMessagesLengthRef = useRef(0);

  // 智能自动滚动
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    // 检查是否在底部附近 (阈值 100px)
    const isNearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 100;
    const isNewMessage = messages.length > prevMessagesLengthRef.current;

    // 只有在新消息到达，或者用户本来就在底部时，才自动滚动
    if (isNewMessage || isNearBottom) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }

    prevMessagesLengthRef.current = messages.length;
  }, [messages, isTyping]);

  return (
    <div
      ref={containerRef}
      className="flex-1 min-h-0 overflow-y-auto p-4 space-y-4 custom-scrollbar flex flex-col"
    >
      {messages.length === 0 ? (
        // 欢迎界面
        <div className="flex-1 flex flex-col items-center justify-center text-center px-8">
          <motion.div
            initial={{ scale: 0.9, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ duration: 0.5 }}
            className="mb-6 max-w-lg"
          >
            <p className="text-gray-500 text-lg leading-relaxed">
              我是您的智能金融助手，可以帮您分析财报、查询行情、智能选股和执行交易。
              <br />
              请在下方直接输入您的需求。
            </p>
          </motion.div>
        </div>
      ) : (
        // 消息列表
        <AnimatePresence>
          {messages.map((message) => (
            <MessageItem key={message.id} message={message} />
          ))}
        </AnimatePresence>
      )}

      {/* 正在输入指示器 */}
      {isTyping && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0 }}
          className="flex items-center gap-2 text-gray-500 text-sm"
        >
          <div className="flex gap-1">
            <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
            <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
            <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
          </div>
          <span>AI正在思考...</span>
        </motion.div>
      )}

      <div ref={messagesEndRef} />
    </div>
  );
};

export default MessageList;

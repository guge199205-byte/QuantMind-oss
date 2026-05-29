/**
 * 单条消息组件
 */

import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { motion } from 'framer-motion';
import { Bot, User } from 'lucide-react';
import { Message } from '../../types';
import { RichContentRenderer } from '../RichContent';

interface MessageItemProps {
  message: Message;
}

const MessageItem: React.FC<MessageItemProps> = ({ message }) => {
  const isUser = message.type === 'user';
  const isSystem = message.type === 'system';
  const markdownTextClass = isUser ? 'text-white' : 'text-slate-900';
  const mutedTextClass = isUser ? 'text-blue-100/90' : 'text-slate-600';
  const strongTextClass = isUser ? 'text-white' : 'text-slate-900';
  const inlineCodeClass = isUser
    ? 'rounded bg-white/15 px-1.5 py-0.5 text-[0.95em] text-white'
    : 'rounded bg-slate-100 px-1.5 py-0.5 text-[0.95em] text-blue-700';
  const preClass = isUser
    ? 'overflow-x-auto rounded-xl bg-slate-900/80 p-3 text-sm text-slate-100'
    : 'overflow-x-auto rounded-xl bg-slate-900 p-3 text-sm text-slate-100';
  const formatFileSize = (size?: number) => {
    if (!size) return '';
    if (size < 1024) return `${size} B`;
    if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
    return `${(size / (1024 * 1024)).toFixed(1)} MB`;
  };

  if (isSystem) {
    return (
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.95 }}
        className="flex justify-center"
      >
        <div className="bg-gray-100 text-gray-600 px-4 py-2 rounded-full text-sm max-w-md text-center">
          {message.content}
        </div>
      </motion.div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, scale: 0.95 }}
      transition={{ duration: 0.3 }}
      className={`flex gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}
    >
      {/* 头像 */}
      <div
        className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${isUser
            ? 'bg-gradient-to-br from-blue-500 to-purple-600'
            : 'bg-gradient-to-br from-gray-700 to-gray-900'
          }`}
      >
        {isUser ? (
          <User className="w-5 h-5 text-white" />
        ) : (
          <Bot className="w-5 h-5 text-white" />
        )}
      </div>

      {/* 消息内容 */}
      <div className={`flex-1 ${isUser ? 'flex justify-end' : 'flex justify-start'}`}>
        <div
          className={`max-w-[80%] rounded-2xl px-4 py-3 ${isUser
              ? 'bg-gradient-to-br from-blue-500 to-purple-600 text-white rounded-tr-sm'
              : 'bg-white border border-gray-200 text-slate-900 rounded-tl-sm shadow-sm'
            }`}
        >
          {message.attachments && message.attachments.length > 0 && (
            <div className="mb-3 flex flex-wrap gap-2">
              {message.attachments.map((attachment, index) => (
                <div
                  key={`${attachment.file_id || attachment.original_name}-${index}`}
                  className={`rounded-xl border px-3 py-2 text-xs ${
                    isUser
                      ? 'border-white/20 bg-white/10 text-white'
                      : 'border-slate-200 bg-slate-50 text-slate-600'
                  }`}
                >
                  <div className="font-medium">{attachment.original_name}</div>
                  <div className={isUser ? 'text-blue-100/90' : 'text-slate-400'}>
                    {[attachment.content_type, formatFileSize(attachment.file_size)].filter(Boolean).join(' · ')}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* 消息文本 - Markdown渲染 */}
          <div className={`prose prose-sm max-w-none break-words ${markdownTextClass}`}>
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                p: ({ children }) => (
                  <p className={`mb-3 leading-7 last:mb-0 ${markdownTextClass}`}>{children}</p>
                ),
                ul: ({ children }) => (
                  <ul className={`mb-3 list-disc pl-5 last:mb-0 ${markdownTextClass}`}>{children}</ul>
                ),
                ol: ({ children }) => (
                  <ol className={`mb-3 list-decimal pl-5 last:mb-0 ${markdownTextClass}`}>{children}</ol>
                ),
                li: ({ children }) => (
                  <li className={`mb-1 leading-7 ${markdownTextClass}`}>{children}</li>
                ),
                strong: ({ children }) => (
                  <strong className={`font-semibold ${strongTextClass}`}>{children}</strong>
                ),
                a: ({ href, children }) => (
                  <a
                    href={href}
                    target="_blank"
                    rel="noreferrer"
                    className={isUser ? 'text-white underline underline-offset-2' : 'text-blue-600 underline underline-offset-2'}
                  >
                    {children}
                  </a>
                ),
                code: (props: any) => {
                  const { inline, children } = props;
                  if (inline) {
                    return <code className={inlineCodeClass}>{children}</code>;
                  }
                  return <code className="bg-transparent p-0 text-inherit">{children}</code>;
                },
                pre: ({ children }) => (
                  <pre className={preClass}>{children}</pre>
                ),
                h1: ({ children }) => (
                  <h1 className={`mb-3 text-xl font-bold leading-8 ${strongTextClass}`}>{children}</h1>
                ),
                h2: ({ children }) => (
                  <h2 className={`mb-3 text-lg font-bold leading-8 ${strongTextClass}`}>{children}</h2>
                ),
                h3: ({ children }) => (
                  <h3 className={`mb-2 text-base font-semibold leading-7 ${strongTextClass}`}>{children}</h3>
                ),
                blockquote: ({ children }) => (
                  <blockquote className={`mb-3 border-l-4 pl-4 ${isUser ? 'border-white/30 text-white/90' : 'border-slate-300 text-slate-600'}`}>
                    {children}
                  </blockquote>
                ),
              }}
            >
              {message.content}
            </ReactMarkdown>
          </div>

          {/* 时间戳 */}
          <div
            className={`text-xs mt-2 ${isUser ? 'text-blue-100' : 'text-gray-400'
              }`}
          >
            {(() => {
              try {
                const date = new Date(message.timestamp);
                return isNaN(date.getTime()) ? '' : date.toLocaleTimeString('zh-CN', {
                  hour: '2-digit',
                  minute: '2-digit',
                });
              } catch (e) {
                return '';
              }
            })()}
          </div>

          {/* 富文本内容渲染 */}
          {message.richContent && (
            <div className="mt-3">
              <RichContentRenderer content={message.richContent} />
            </div>
          )}
        </div>
      </div>
    </motion.div>
  );
};

export default MessageItem;

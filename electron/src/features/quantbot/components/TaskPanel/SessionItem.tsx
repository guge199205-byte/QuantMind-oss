/**
 * SessionItem - 单个会话条目组件 (适配 QuantBot)
 * 路径: electron/src/features/quantbot/components/TaskPanel/SessionItem.tsx
 */

import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { MessageCircle, MoreVertical, Trash2, Edit, Check, X } from 'lucide-react';
import { useSessionStore } from '../../store/sessionStore';
import type { Session } from '../../services/agentApi';
import { message } from 'antd';

interface SessionItemProps {
    session: Session;
}

const SessionItem: React.FC<SessionItemProps> = ({ session }) => {
    const { currentSessionId, switchSession, deleteSession, updateSessionTitle } = useSessionStore();
    const [showMenu, setShowMenu] = useState(false);
    const [isEditing, setIsEditing] = useState(false);
    const [editTitle, setEditTitle] = useState(session.name || '新对话');

    // 适配 id 或 session_id
    const sid = session.id || (session as any).session_id;
    const isActive = sid === currentSessionId;

    const handleClick = () => {
        if (!isEditing && sid) {
            switchSession(sid);
        }
    };

    const handleDelete = async (e: React.MouseEvent) => {
        e.stopPropagation();
        setShowMenu(false);
        if (!sid) return;
        
        if (window.confirm(`确定要删除对话 "${session.name || '新对话'}" 吗？`)) {
            try {
                await deleteSession(sid);
                message.success('已删除对话');
            } catch (error) {
                console.error('Delete failed:', error);
                message.error('删除失败');
            }
        }
    };

    const handleStartEdit = (e: React.MouseEvent) => {
        e.stopPropagation();
        setIsEditing(true);
        setShowMenu(false);
    };

    const handleSaveEdit = async () => {
        if (editTitle.trim() && editTitle !== (session.name || '新对话') && sid) {
            try {
                await updateSessionTitle(sid, editTitle.trim());
                message.success('已更新标题');
            } catch (error) {
                console.error('Update title failed:', error);
            }
        }
        setIsEditing(false);
    };

    const handleCancelEdit = () => {
        setEditTitle(session.name || '新对话');
        setIsEditing(false);
    };

    const formatTime = (dateStr?: string) => {
        if (!dateStr) return '未知时间';
        const date = new Date(dateStr);
        const now = new Date();
        const diff = now.getTime() - date.getTime();
        const minutes = Math.floor(diff / 60000);
        const hours = Math.floor(diff / 3600000);

        if (minutes < 1) return '刚刚';
        if (minutes < 60) return `${minutes}分钟前`;
        if (hours < 24) return `${hours}小时前`;

        return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' });
    };

    return (
        <motion.div
            initial={{ opacity: 0, y: -5 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, height: 0 }}
            className={`group relative p-3 rounded-xl cursor-pointer transition-all ${isActive
                ? 'bg-blue-50 border border-blue-200'
                : 'hover:bg-slate-50 border border-transparent'
                }`}
            onClick={handleClick}
        >
            <div className="flex items-start gap-3">
                <div className={`mt-1 p-1.5 rounded-lg ${isActive ? 'bg-blue-100 text-blue-600' : 'bg-slate-100 text-slate-400 group-hover:bg-white group-hover:shadow-sm'}`}>
                   <MessageCircle className="w-4 h-4" />
                </div>

                <div className="flex-1 min-w-0">
                    {isEditing ? (
                        <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                            <input
                                type="text"
                                value={editTitle}
                                onChange={(e) => setEditTitle(e.target.value)}
                                onKeyDown={(e) => {
                                    if (e.key === 'Enter') handleSaveEdit();
                                    if (e.key === 'Escape') handleCancelEdit();
                                }}
                                className="flex-1 px-2 py-1 text-sm border border-blue-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
                                autoFocus
                            />
                            <button onClick={handleSaveEdit} className="p-1 hover:bg-green-100 rounded text-green-600">
                                <Check className="w-3.5 h-3.5" />
                            </button>
                            <button onClick={handleCancelEdit} className="p-1 hover:bg-red-100 rounded text-red-600">
                                <X className="w-3.5 h-3.5" />
                            </button>
                        </div>
                    ) : (
                        <>
                            <h4 className={`text-sm font-semibold truncate ${isActive ? 'text-blue-900' : 'text-slate-700'}`}>
                                {session.name || '新对话'}
                            </h4>
                            <p className="text-[11px] text-slate-400 mt-0.5">
                                {formatTime(session.updated_at || session.created_at)}
                            </p>
                        </>
                    )}
                </div>

                {!isEditing && (
                    <div className="relative">
                        <button
                            onClick={(e) => {
                                e.stopPropagation();
                                setShowMenu(!showMenu);
                            }}
                            className={`p-1 rounded-md opacity-0 group-hover:opacity-100 transition-opacity ${showMenu ? 'opacity-100 bg-white shadow-sm' : 'hover:bg-white hover:shadow-sm'}`}
                        >
                            <MoreVertical className="w-4 h-4 text-slate-500" />
                        </button>

                        {showMenu && (
                            <div className="absolute right-0 mt-1 w-32 bg-white border border-slate-100 rounded-xl shadow-xl z-20 overflow-hidden" onClick={(e) => e.stopPropagation()}>
                                <button onClick={handleStartEdit} className="w-full flex items-center gap-2 px-3 py-2 text-xs text-slate-700 hover:bg-slate-50 transition-colors">
                                    <Edit className="w-3.5 h-3.5" />
                                    重命名
                                </button>
                                <button onClick={handleDelete} className="w-full flex items-center gap-2 px-3 py-2 text-xs text-rose-600 hover:bg-rose-50 transition-colors">
                                    <Trash2 className="w-3.5 h-3.5" />
                                    删除
                                </button>
                            </div>
                        )}
                    </div>
                )}
            </div>

            {/* 点击外部关闭菜单 */}
            {showMenu && (
                <div className="fixed inset-0 z-10" onClick={() => setShowMenu(false)} />
            )}
        </motion.div>
    );
};

export default SessionItem;

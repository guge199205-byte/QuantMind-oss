/**
 * SessionList - 会话列表组件
 */

import React, { useEffect, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { MessageCircle } from 'lucide-react';
import { useSelector } from 'react-redux';
import { useSessionStore } from '../../store/sessionStore';
import SessionItem from './SessionItem';
import type { Session } from '../../services/agentApi';
import { RootState } from '../../../../store';

const SessionList: React.FC = () => {
    const { sessions, fetchSessions, loading } = useSessionStore();
    const isAuthReady = useSelector((state: RootState) => state.auth.isInitialized && state.auth.isAuthenticated);

    useEffect(() => {
        if (!isAuthReady) return;
        // 组件挂载时加载会话列表
        fetchSessions();
    }, [fetchSessions, isAuthReady]);

    // 按时间分组
    const groupedSessions = useMemo(() => {
        const now = new Date();
        const today: Session[] = [];
        const week: Session[] = [];
        const older: Session[] = [];

        // 防御性校验
        if (!Array.isArray(sessions)) return { today, week, older };

        // 先按更新时间降序排列
        const sortedSessions = [...sessions].sort((a, b) => {
            const timeA = new Date(a.updated_at || a.created_at || 0).getTime();
            const timeB = new Date(b.updated_at || b.created_at || 0).getTime();
            return timeB - timeA;
        });

        sortedSessions.forEach(session => {
            const updatedDate = new Date(session.updated_at || session.created_at || now);
            const diffDays = Math.floor((now.getTime() - updatedDate.getTime()) / (1000 * 60 * 60 * 24));

            if (diffDays === 0) {
                today.push(session);
            } else if (diffDays <= 7) {
                week.push(session);
            } else {
                older.push(session);
            }
        });

        return { today, week, older };
    }, [sessions]);

    if (loading && (!sessions || !Array.isArray(sessions) || sessions.length === 0)) {
        return (
            <div className="flex items-center justify-center py-8">
                <div className="text-sm text-gray-400">加载中...</div>
            </div>
        );
    }

    if (!sessions || !Array.isArray(sessions) || sessions.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center py-8 text-center">
                <MessageCircle className="w-12 h-12 text-gray-300 mb-2" />
                <p className="text-sm text-gray-400">{isAuthReady ? '暂无对话' : '请先登录后使用 QuantBot'}</p>
                <p className="text-xs text-gray-300 mt-1">{isAuthReady ? '点击上方按钮开始新对话' : '登录完成后会自动加载会话'}</p>
            </div>
        );
    }

    return (
        <div className="flex-1 overflow-y-auto px-2 py-2">
            <AnimatePresence>
                {/* 今天 */}
                {groupedSessions.today.length > 0 && (
                    <SessionGroup key="group-today" title="今天" sessions={groupedSessions.today} />
                )}

                {/* 最近7天 */}
                {groupedSessions.week.length > 0 && (
                    <SessionGroup key="group-week" title="最近7天" sessions={groupedSessions.week} />
                )}

                {/* 更早 */}
                {groupedSessions.older.length > 0 && (
                    <SessionGroup key="group-older" title="更早" sessions={groupedSessions.older} />
                )}
            </AnimatePresence>
        </div>
    );
};

interface SessionGroupProps {
    title: string;
    sessions: Session[];
}

const buildSessionKey = (session: Session, index: number): string => {
    const primaryId = String(session.id || (session as any).session_id || '').trim();
    if (primaryId) return primaryId;
    const name = String(session.name || 'session').trim() || 'session';
    const stamp = String(session.updated_at || session.created_at || Date.now());
    return `session-fallback-${name}-${stamp}-${index}`;
};

const SessionGroup: React.FC<SessionGroupProps> = ({ title, sessions }) => {
    return (
        <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, height: 0 }}
            className="mb-4"
        >
            <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2 px-2">
                {title}
            </h4>
            <div className="space-y-1">
                {sessions.map((session, index) => (
                    <SessionItem key={buildSessionKey(session, index)} session={session} />
                ))}
            </div>
        </motion.div>
    );
};

export default SessionList;

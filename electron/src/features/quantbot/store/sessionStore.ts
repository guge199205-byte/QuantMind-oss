/**
 * 会话管理 Store (Zustand) - 最终稳定版
 * 路径: electron/src/features/quantbot/store/sessionStore.ts
 */

import { create } from 'zustand';
import agentApi, { Session } from '../services/agentApi';

interface SessionStore {
    sessions: Session[];
    currentSessionId: string | null;
    loading: boolean;
    error: string | null;

    // Actions
    fetchSessions: (forceKeepId?: boolean) => Promise<void>;
    createSession: (name?: string) => Promise<Session>;
    switchSession: (sessionId: string) => void;
    deleteSession: (sessionId: string) => Promise<void>;
    updateSessionTitle: (sessionId: string, title: string) => Promise<void>;
    setCurrentSessionId: (sessionId: string | null) => void;
}

export const useSessionStore = create<SessionStore>((set, get) => {
    return {
        sessions: [],
        currentSessionId: agentApi.getChatId(),
        loading: false,
        error: null,

        fetchSessions: async (forceKeepId: boolean = true) => {
            if (get().loading) return;
            set({ loading: true });
            try {
                const sessions = await agentApi.getSessions(20);
                const { currentSessionId } = get();
                
                // 策略：刷新列表时保留现有的 ID，除非当前没有 ID 且列表里有新数据
                let activeId = currentSessionId;
                
                if (!activeId && sessions.length > 0) {
                    activeId = sessions[0].id;
                }

                if (activeId) {
                    agentApi.setChatId(activeId);
                }

                set({ 
                    sessions, 
                    currentSessionId: activeId, 
                    loading: false 
                });
            } catch (error: any) {
                set({ loading: false });
            }
        },

        createSession: async (name: string = '新对话') => {
            set({ loading: true, error: null });
            try {
                const newSession = await agentApi.createNewSession(name);
                const sid = newSession.id;

                set(state => ({
                    sessions: [newSession, ...state.sessions],
                    currentSessionId: sid,
                    loading: false
                }));

                return newSession;
            } catch (error: any) {
                set({ loading: false });
                throw error;
            }
        },

        switchSession: (sessionId: string) => {
            if (!sessionId) return;
            agentApi.setChatId(sessionId);
            set({ currentSessionId: sessionId });
        },

        deleteSession: async (sessionId: string) => {
            if (!sessionId) return;
            set({ loading: true });
            try {
                await agentApi.deleteSession(sessionId);
                const { sessions, currentSessionId } = get();
                const newSessions = sessions.filter(s => s.id !== sessionId);
                const newCurrentId = currentSessionId === sessionId ? (newSessions[0]?.id || null) : currentSessionId;
                
                if (newCurrentId) agentApi.setChatId(newCurrentId);
                else agentApi.resetSession();

                set({ sessions: newSessions, currentSessionId: newCurrentId, loading: false });
            } catch (error) {
                set({ loading: false });
            }
        },

        updateSessionTitle: async (sessionId: string, title: string) => {
            if (!sessionId || !title.trim()) return;

            set(state => ({
                sessions: state.sessions.map(s =>
                    s.id === sessionId ? { ...s, name: title } : s
                )
            }));

            const updated = await agentApi.updateSessionTitle(sessionId, title.trim());
            if (!updated) {
                await get().fetchSessions();
            }
        },

        setCurrentSessionId: (sessionId: string | null) => {
            if (sessionId) agentApi.setChatId(sessionId);
            else agentApi.resetSession();
            set({ currentSessionId: sessionId });
        }
    };
});

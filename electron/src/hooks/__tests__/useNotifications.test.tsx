import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { useNotifications } from '../useNotifications';
import { NotificationListResponse, userService, UserNotification } from '../../services/userService';
import { websocketService } from '../../services/websocketService';

// Mock userService
vi.mock('../../services/userService', () => ({
    userService: {
        getNotifications: vi.fn(),
        markNotificationRead: vi.fn(),
        markAllNotificationsRead: vi.fn()
    }
}));

vi.mock('../../services/websocketService', () => ({
    websocketService: {
        getStatus: vi.fn(() => 'connected'),
        connect: vi.fn(() => Promise.resolve()),
        subscribe: vi.fn(),
        unsubscribe: vi.fn(),
        addMessageHandler: vi.fn(),
        removeMessageHandler: vi.fn(),
        addStatusHandler: vi.fn(),
        removeStatusHandler: vi.fn(),
    },
    MessageType: {
        NOTIFICATION: 'notification',
    },
    WebSocketStatus: {
        CONNECTED: 'connected',
        DISCONNECTED: 'disconnected',
        ERROR: 'error',
        RECONNECTING: 'reconnecting',
    },
}));

vi.mock('../../services/refreshOrchestrator', () => ({
    refreshOrchestrator: {
        register: vi.fn(() => () => undefined),
        requestRefresh: vi.fn(() => Promise.resolve()),
    },
}));

describe('useNotifications', () => {
    const storage = new Map<string, string>();
    const mockNotifications: UserNotification[] = [
        {
            id: 1,
            title: 'Test Notification 1',
            content: 'Message 1',
            type: 'trading',
            level: 'warning',
            is_read: false,
            created_at: '2025-02-13T10:00:00Z',
        },
        {
            id: 2,
            title: 'Test Notification 2',
            content: 'Message 2',
            type: 'system',
            level: 'info',
            is_read: true,
            created_at: '2025-02-13T09:00:00Z',
        }
    ];

    const mockResponse: NotificationListResponse = {
        items: mockNotifications,
        total: 2,
        unread_count: 1,
        has_more: false,
    };

    beforeEach(() => {
        vi.clearAllMocks();
        storage.clear();
        vi.stubGlobal('localStorage', {
            getItem: vi.fn((key: string) => storage.get(key) ?? null),
            setItem: vi.fn((key: string, value: string) => {
                storage.set(key, value);
            }),
            removeItem: vi.fn((key: string) => {
                storage.delete(key);
            }),
        });
        localStorage.setItem('user', JSON.stringify({ id: '1001' }));
    });

    it('should fetch notifications successfully', async () => {
        vi.mocked(userService.getNotifications).mockResolvedValue({
            success: true,
            data: mockResponse,
            timestamp: new Date().toISOString()
        });

        const { result } = renderHook(() => useNotifications({ autoRefresh: false }));

        expect(result.current.loading).toBe(true);
        expect(result.current.notifications).toEqual([]);

        await waitFor(() => {
            expect(result.current.loading).toBe(false);
        });

        expect(result.current.notifications).toEqual(mockNotifications);
        expect(result.current.unreadCount).toBe(1);
        expect(result.current.total).toBe(2);
        expect(result.current.error).toBeNull();
        expect(result.current.degraded).toBe(false);
    });

    it('should handle API failure gracefully', async () => {
        vi.mocked(userService.getNotifications).mockResolvedValue({
            success: false,
            error: 'Backend offline',
            timestamp: new Date().toISOString()
        });

        const { result } = renderHook(() => useNotifications({ autoRefresh: false }));

        await waitFor(() => {
            expect(result.current.loading).toBe(false);
        });

        expect(result.current.error).toBe('Backend offline');
        expect(result.current.degraded).toBe(true);
        expect(result.current.notifications).toEqual([]);
    });

    it('should handle network exception gracefully', async () => {
        vi.mocked(userService.getNotifications).mockRejectedValue(new Error('Network error'));

        const { result } = renderHook(() => useNotifications({ autoRefresh: false }));

        await waitFor(() => {
            expect(result.current.loading).toBe(false);
        });

        expect(result.current.error).toBe('Network error');
        expect(result.current.degraded).toBe(true);
    });

    it('should mark notification as read optimistically', async () => {
        vi.mocked(userService.getNotifications).mockResolvedValue({
            success: true,
            data: mockResponse,
            timestamp: new Date().toISOString()
        });
        vi.mocked(userService.markNotificationRead).mockResolvedValue({
            success: true,
            timestamp: new Date().toISOString()
        });

        const { result } = renderHook(() => useNotifications({ autoRefresh: false }));

        await waitFor(() => {
            expect(result.current.loading).toBe(false);
        });

        // Mark ID 1 as read (was false)
        await act(async () => {
            await result.current.markAsRead(1);
        });

        // Should be updated in state
        expect(result.current.notifications[0].is_read).toBe(true);
        expect(result.current.unreadCount).toBe(0);

        // API called
        expect(userService.markNotificationRead).toHaveBeenCalledWith(1);
    });

    it('should mark all notifications as read optimistically', async () => {
        vi.mocked(userService.getNotifications).mockResolvedValue({
            success: true,
            data: mockResponse,
            timestamp: new Date().toISOString()
        });
        vi.mocked(userService.markAllNotificationsRead).mockResolvedValue({
            success: true,
            data: { count: 1 },
            timestamp: new Date().toISOString()
        });

        const { result } = renderHook(() => useNotifications({ autoRefresh: false }));

        await waitFor(() => {
            expect(result.current.loading).toBe(false);
        });

        await act(async () => {
            await result.current.markAllAsRead();
        });

        expect(result.current.notifications.every(n => n.is_read)).toBe(true);
        expect(result.current.unreadCount).toBe(0);
        expect(userService.markAllNotificationsRead).toHaveBeenCalled();
    });

    it('should prepend realtime notifications from websocket', async () => {
        let realtimeHandler: ((data: unknown) => void) | undefined;
        vi.mocked(websocketService.addMessageHandler).mockImplementation((_, handler) => {
            realtimeHandler = handler as (data: unknown) => void;
        });
        vi.mocked(userService.getNotifications).mockResolvedValue({
            success: true,
            data: mockResponse,
            timestamp: new Date().toISOString()
        });

        const { result } = renderHook(() => useNotifications({ autoRefresh: false }));

        await waitFor(() => {
            expect(result.current.loading).toBe(false);
        });

        act(() => {
            realtimeHandler?.({
                id: 3,
                title: 'Realtime Notification',
                content: 'New content',
                type: 'strategy',
                level: 'success',
                is_read: false,
                created_at: '2025-02-13T11:00:00Z',
            });
        });

        expect(result.current.notifications[0].id).toBe(3);
        expect(result.current.notifications[0].content).toBe('New content');
        expect(result.current.unreadCount).toBe(2);
    });
});

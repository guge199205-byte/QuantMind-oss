import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useTradeWebSocket } from '../useTradeWebSocket';
import { websocketService, MessageType } from '../../services/websocketService';

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
        TRADE_UPDATE: 'trade_update',
    },
}));

describe('useTradeWebSocket', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('应主动连接并订阅当前用户的实盘推送主题', () => {
        renderHook(() =>
            useTradeWebSocket({
                userId: '79311845',
                onTradeEvent: vi.fn(),
            }),
        );

        expect(websocketService.connect).toHaveBeenCalledTimes(1);
        expect(websocketService.addMessageHandler).toHaveBeenCalledTimes(1);
        expect(websocketService.addStatusHandler).toHaveBeenCalledTimes(1);
        expect(websocketService.subscribe).toHaveBeenCalledWith({ channels: ['trade.updates.79311845'] });
    });

    it('应将 trade_update 消息转发给回调', () => {
        const onTradeEvent = vi.fn();
        let capturedHandler: ((data: unknown) => void) | undefined;
        vi.mocked(websocketService.addMessageHandler).mockImplementation((_, handler) => {
            capturedHandler = handler as (data: unknown) => void;
        });

        renderHook(() =>
            useTradeWebSocket({
                userId: '79311845',
                onTradeEvent,
            }),
        );

        act(() => {
            capturedHandler?.({
                data: {
                    event_type: 'ACCOUNT_UPDATED',
                    user_id: '79311845',
                },
            });
        });

        expect(onTradeEvent).toHaveBeenCalledWith(
            expect.objectContaining({
                event_type: 'ACCOUNT_UPDATED',
                user_id: '79311845',
            }),
        );
    });

    it('卸载时应清理订阅与消息处理器', () => {
        let capturedHandler: ((data: unknown) => void) | undefined;
        vi.mocked(websocketService.addMessageHandler).mockImplementation((_, handler) => {
            capturedHandler = handler as (data: unknown) => void;
        });

        const { unmount } = renderHook(() =>
            useTradeWebSocket({
                userId: '79311845',
                onTradeEvent: vi.fn(),
            }),
        );

        unmount();

        expect(websocketService.removeMessageHandler).toHaveBeenCalledWith(
            MessageType.TRADE_UPDATE,
            capturedHandler,
        );
        expect(websocketService.unsubscribe).toHaveBeenCalledWith(['trade.updates.79311845']);
    });
});

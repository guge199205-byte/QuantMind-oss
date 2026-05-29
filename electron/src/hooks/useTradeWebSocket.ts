import { useEffect, useRef, useCallback } from 'react';
import { websocketService, MessageType } from '../services/websocketService';

export interface TradeEvent {
  event_type: string;       // e.g. 'TRADE_CREATED'
  trade_id?: string;
  order_id?: string;
  portfolio_id?: string;
  user_id?: string;
  symbol?: string;
  side?: string;
  quantity?: string;
  price?: string;
  timestamp?: string;
}

interface UseTradeWebSocketOptions {
  /** 当前登录用户 ID（字符串形式） */
  userId: string;
  /** 收到交易事件时的回调 */
  onTradeEvent: (event: TradeEvent) => void;
  /** 是否启用（默认 true） */
  enabled?: boolean;
}

/**
 * 订阅 `trade.updates.{userId}` WebSocket 主题，收到成交/订单事件后调用 onTradeEvent。
 *
 * 消息格式（由 stream service trade_pusher 推送）：
 * ```json
 * { "type": "trade_update", "timestamp": 1234567890, "data": { "event_type": "TRADE_CREATED", ... } }
 * ```
 */
export function useTradeWebSocket({
  userId,
  onTradeEvent,
  enabled = true,
}: UseTradeWebSocketOptions): void {
  const onTradeEventRef = useRef(onTradeEvent);
  onTradeEventRef.current = onTradeEvent;
  const subscriptionReadyRef = useRef(false);

  const handleMessage = useCallback(
    (type: MessageType, data: unknown) => {
      if (type !== MessageType.TRADE_UPDATE) return;
      const payload = data as { data?: TradeEvent };
      const event: TradeEvent = payload?.data ?? (data as TradeEvent);
      if (event?.event_type) {
        onTradeEventRef.current(event);
      }
    },
    []
  );

  const handleTradeUpdate = useCallback(
    (data: unknown) => {
      handleMessage(MessageType.TRADE_UPDATE, data);
    },
    [handleMessage]
  );

  useEffect(() => {
    if (!enabled || !userId) return;

    const topic = `trade.updates.${userId}`;

    // 先确保全局 WS 已建立，再订阅交易主题。
    // 这样即使上层 WebSocketProvider 未自动连接，实盘页也能拿到实时推送。
    void websocketService.connect().catch((error) => {
      console.warn('实盘交易 WS 连接失败，将继续依赖轮询刷新:', error);
    });

    // 等待 WS 连接后再订阅（websocketService 可能尚未建立连接）
    const subscribe = () => {
      if (subscriptionReadyRef.current) return;
      websocketService.subscribe({ channels: [topic] });
      subscriptionReadyRef.current = true;
    };

    // 注册 TRADE_UPDATE 消息处理器
    websocketService.addMessageHandler(MessageType.TRADE_UPDATE, handleTradeUpdate);

    // 如果已连接则立即订阅，否则等待连接事件
    const currentStatus = websocketService.getStatus();
    if (currentStatus === 'connected') {
      subscribe();
    }

    // 监听状态变化，连接建立后补发订阅
    const removeStatusHandler = (() => {
      const handler = (status: string) => {
        if (status === 'connected') subscribe();
      };
      websocketService.addStatusHandler(handler as any);
      return () => websocketService.removeStatusHandler(handler as any);
    })();

    return () => {
      removeStatusHandler();
      websocketService.removeMessageHandler(MessageType.TRADE_UPDATE, handleTradeUpdate);
      if (subscriptionReadyRef.current) {
        websocketService.unsubscribe([topic]);
        subscriptionReadyRef.current = false;
      }
    };
  }, [userId, enabled, handleTradeUpdate]);
}

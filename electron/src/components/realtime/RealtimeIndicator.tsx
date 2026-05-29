/**
 * 实时连接指示器 - Week 9 Day 1
 * 显示WebSocket连接状态
 */

import React from 'react';
import { ConnectionState } from '../../services/websocket/WebSocketClient';

export interface RealtimeIndicatorProps {
  state: ConnectionState;
  showLabel?: boolean;
  size?: 'small' | 'medium' | 'large';
  className?: string;
}

const stateConfig = {
  [ConnectionState.DISCONNECTED]: {
    color: '#999',
    text: '未连接',
    icon: '○'
  },
  [ConnectionState.CONNECTING]: {
    color: '#faad14',
    text: '连接中',
    icon: '⟳'
  },
  [ConnectionState.CONNECTED]: {
    color: '#52c41a',
    text: '已连接',
    icon: '●'
  },
  [ConnectionState.RECONNECTING]: {
    color: '#ff7875',
    text: '重连中',
    icon: '⟳'
  },
  [ConnectionState.FAILED]: {
    color: '#ff4d4f',
    text: '连接失败',
    icon: '✕'
  }
};

const sizeConfig = {
  small: {
    dotSize: '8px',
    fontSize: '12px',
    iconSize: '12px'
  },
  medium: {
    dotSize: '10px',
    fontSize: '14px',
    iconSize: '14px'
  },
  large: {
    dotSize: '12px',
    fontSize: '16px',
    iconSize: '16px'
  }
};

export const RealtimeIndicator: React.FC<RealtimeIndicatorProps> = ({
  state,
  showLabel = true,
  size = 'medium',
  className = ''
}) => {
  const config = stateConfig[state];
  const sizeStyle = sizeConfig[size];

  const isAnimating = state === ConnectionState.CONNECTING || state === ConnectionState.RECONNECTING;

  return (
    <div
      className={`inline-flex items-center gap-2 ${className}`}
      style={{ fontSize: sizeStyle.fontSize }}
    >
      <span
        className={`inline-block ${isAnimating ? 'animate-spin' : ''}`}
        style={{
          width: sizeStyle.dotSize,
          height: sizeStyle.dotSize,
          fontSize: sizeStyle.iconSize,
          color: config.color,
          lineHeight: 1
        }}
      >
        {config.icon}
      </span>
      {showLabel && (
        <span style={{ color: config.color }}>
          {config.text}
        </span>
      )}
    </div>
  );
};

export default RealtimeIndicator;

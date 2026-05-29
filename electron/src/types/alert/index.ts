/**
 * 告警通知系统类型定义
 */

export type AlertType = 'price' | 'indicator' | 'custom';
export type AlertStatus = 'active' | 'inactive' | 'triggered';
export type AlertOperator = 'above' | 'below' | 'cross_above' | 'cross_below' | 'equal' | 'not_equal';
export type NotificationType = 'info' | 'warning' | 'error' | 'success';
export type NotificationMethod = 'desktop' | 'sound' | 'email';

export interface AlertCondition {
  symbol: string;
  operator: AlertOperator;
  value: number;
  indicator?: string;
  timeframe?: string;
}

export interface Alert {
  id: string;
  name: string;
  description?: string;
  type: AlertType;
  condition: AlertCondition;
  status: AlertStatus;
  enabled: boolean;
  notificationMethods: NotificationMethod[];
  createdAt: number;
  updatedAt: number;
  triggeredAt?: number;
  triggerCount: number;
  lastTriggerValue?: number;
}

export interface AlertTrigger {
  alertId: string;
  timestamp: number;
  value: number;
  previousValue?: number;
  message: string;
}

export interface Notification {
  id: string;
  alertId?: string;
  title: string;
  message: string;
  type: NotificationType;
  timestamp: number;
  read: boolean;
  dismissed: boolean;
  data?: Record<string, any>;
}

export interface NotificationConfig {
  enableDesktop: boolean;
  enableSound: boolean;
  enableEmail: boolean;
  soundFile?: string;
  emailAddress?: string;
  maxNotifications: number;
  autoCloseDelay?: number;
}

export interface PriceAlertConfig {
  symbol: string;
  targetPrice: number;
  operator: 'above' | 'below';
  currentPrice: number;
}

export interface IndicatorAlertConfig {
  symbol: string;
  indicator: string;
  operator: AlertOperator;
  value: number;
  period?: number;
}

export interface CustomAlertConfig {
  symbol: string;
  expression: string;
  description: string;
}

export interface AlertHistory {
  id: string;
  alertId: string;
  alertName: string;
  triggerTime: number;
  value: number;
  message: string;
}

export interface AlertStatistics {
  totalAlerts: number;
  activeAlerts: number;
  triggeredToday: number;
  triggeredThisWeek: number;
  triggeredThisMonth: number;
  mostTriggeredAlert?: {
    id: string;
    name: string;
    count: number;
  };
}

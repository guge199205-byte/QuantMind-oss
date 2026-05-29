import React, { useState, useEffect } from 'react';
import { Alert, Button, Space } from 'antd';
import {
  CloseCircleOutlined,
  WifiOutlined,
  LockOutlined,
  ClockCircleOutlined,
  ExclamationCircleOutlined,
  ReloadOutlined
} from '@ant-design/icons';

/**
 * 错误提示组件
 * 提供友好的错误提示和处理机制
 */

export type ErrorType = 'network' | 'data' | 'permission' | 'timeout' | 'unknown';

interface ErrorMessageProps {
  type?: ErrorType;
  message?: string;
  description?: string;
  showIcon?: boolean;
  closable?: boolean;
  onRetry?: () => void;
  onClose?: () => void;
  retryText?: string;
  autoRetry?: boolean;
  retryDelay?: number;
  maxRetries?: number;
}

const ErrorIcons = {
  network: <WifiOutlined />,
  data: <ExclamationCircleOutlined />,
  permission: <LockOutlined />,
  timeout: <ClockCircleOutlined />,
  unknown: <CloseCircleOutlined />
};

const DefaultMessages = {
  network: {
    title: '网络连接失败',
    description: '无法连接到服务器，请检查您的网络连接'
  },
  data: {
    title: '数据加载失败',
    description: '无法加载数据，请稍后重试'
  },
  permission: {
    title: '权限不足',
    description: '您没有权限访问此资源'
  },
  timeout: {
    title: '请求超时',
    description: '服务器响应超时，请稍后重试'
  },
  unknown: {
    title: '发生错误',
    description: '出现了未知错误，请稍后重试'
  }
};

export const ErrorMessage: React.FC<ErrorMessageProps> = ({
  type = 'unknown',
  message,
  description,
  showIcon = true,
  closable = true,
  onRetry,
  onClose,
  retryText = '重试',
  autoRetry = false,
  retryDelay = 3000,
  maxRetries = 3
}) => {
  const [retryCount, setRetryCount] = useState(0);
  const [isRetrying, setIsRetrying] = useState(false);
  const [countdown, setCountdown] = useState(0);

  const defaultMessage = DefaultMessages[type];
  const finalMessage = message || defaultMessage.title;
  const finalDescription = description || defaultMessage.description;

  useEffect(() => {
    if (autoRetry && onRetry && retryCount < maxRetries) {
      setCountdown(retryDelay / 1000);
      const countdownTimer = setInterval(() => {
        (setCountdown as any)((prev) => {
          if (prev <= 1) {
            clearInterval(countdownTimer);
            handleRetry();
            return 0;
          }
          return prev - 1;
        });
      }, 1000);

      return () => clearInterval(countdownTimer);
    }
  }, [autoRetry, retryCount, retryDelay, maxRetries]);

  const handleRetry = async () => {
    if (onRetry && !isRetrying) {
      setIsRetrying(true);
      (setRetryCount as any)((prev) => prev + 1);
      try {
        await onRetry();
      } catch (error) {
        console.error('Retry failed:', error);
      } finally {
        setIsRetrying(false);
      }
    }
  };

  const actionButtons = (
    <Space>
      {onRetry && (
        <Button
          size="small"
          type="primary"
          icon={<ReloadOutlined spin={isRetrying} />}
          onClick={handleRetry}
          disabled={isRetrying || (autoRetry && retryCount >= maxRetries)}
        >
          {isRetrying ? '重试中...' : retryText}
          {autoRetry && countdown > 0 && ` (${countdown}s)`}
        </Button>
      )}
    </Space>
  );

  return (
    <Alert
      message={finalMessage}
      description={
        <div>
          <div>{finalDescription}</div>
          {autoRetry && retryCount < maxRetries && (
            <div style={{ marginTop: 8, fontSize: 12, color: '#666' }}>
              将在 {countdown} 秒后自动重试 (尝试 {retryCount + 1}/{maxRetries})
            </div>
          )}
          {autoRetry && retryCount >= maxRetries && (
            <div style={{ marginTop: 8, fontSize: 12, color: '#ff4d4f' }}>
              已达到最大重试次数，请手动刷新页面
            </div>
          )}
        </div>
      }
      type="error"
      showIcon={showIcon}
      icon={ErrorIcons[type]}
      closable={closable}
      onClose={onClose}
      action={actionButtons}
      style={{ marginBottom: 16 }}
    />
  );
};

// 网络错误
export const NetworkError: React.FC<Omit<ErrorMessageProps, 'type'>> = (props) => {
  return <ErrorMessage type="network" {...props} />;
};

// 数据错误
export const DataError: React.FC<Omit<ErrorMessageProps, 'type'>> = (props) => {
  return <ErrorMessage type="data" {...props} />;
};

// 权限错误
export const PermissionError: React.FC<Omit<ErrorMessageProps, 'type'>> = (props) => {
  return <ErrorMessage type="permission" {...props} />;
};

// 超时错误
export const TimeoutError: React.FC<Omit<ErrorMessageProps, 'type'>> = (props) => {
  return <ErrorMessage type="timeout" {...props} />;
};

// 简化的错误显示组件
export const SimpleError: React.FC<{
  error: Error | string | null;
  onRetry?: () => void;
}> = ({ error, onRetry }) => {
  if (!error) return null;

  const errorMessage = typeof error === 'string' ? error : error.message;

  return (
    <ErrorMessage
      message="操作失败"
      description={errorMessage}
      onRetry={onRetry}
      autoRetry={false}
    />
  );
};

// 内联错误提示
export const InlineError: React.FC<{
  error: string | null;
}> = ({ error }) => {
  if (!error) return null;

  return (
    <div style={{
      color: '#ff4d4f',
      fontSize: 12,
      marginTop: 4,
      display: 'flex',
      alignItems: 'center',
      gap: 4
    }}>
      <CloseCircleOutlined />
      <span>{error}</span>
    </div>
  );
};

export default ErrorMessage;

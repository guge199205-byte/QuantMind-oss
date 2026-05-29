import React from 'react';
import { Wifi, WifiOff, Activity } from 'lucide-react';
import { useServiceStatus } from '../../hooks/useServiceStatus';

interface ServiceStatusIndicatorProps {
  port?: number;
  showLabel?: boolean;
  className?: string;
}

export const ServiceStatusIndicator: React.FC<ServiceStatusIndicatorProps> = ({
  port = 8000,
  showLabel = true,
  className = ''
}) => {
  const { statuses } = useServiceStatus();
  const serviceStatus = statuses.get(`${port}`);

  const getStatusDisplay = () => {
    if (!serviceStatus) {
      return {
        icon: <Activity className="w-4 h-4 text-gray-500 animate-pulse" />,
        text: '检测中...',
        color: 'text-gray-500'
      };
    }

    switch (serviceStatus.status) {
      case 'online':
        return {
          icon: <Wifi className="w-4 h-4 text-green-600" />,
          text: '服务就绪',
          color: 'text-green-600'
        };
      case 'offline':
        return {
          icon: <WifiOff className="w-4 h-4 text-red-600" />,
          text: '服务未就绪',
          color: 'text-red-600'
        };
      case 'checking':
        return {
          icon: <Activity className="w-4 h-4 text-gray-500 animate-pulse" />,
          text: '检测中...',
          color: 'text-gray-500'
        };
      default:
        return {
          icon: <WifiOff className="w-4 h-4 text-gray-400" />,
          text: '未知状态',
          color: 'text-gray-400'
        };
    }
  };

  const { icon, text, color } = getStatusDisplay();

  return (
    <div className={`flex items-center space-x-2 ${className}`}>
      {icon}
      {showLabel && (
        <span className={`font-medium ${color}`}>
          {text}
        </span>
      )}
      {serviceStatus?.responseTime && (
        <span className="text-xs text-gray-400">
          ({serviceStatus.responseTime}ms)
        </span>
      )}
    </div>
  );
};

// 简化版本，只显示图标
export const ServiceStatusIcon: React.FC<{ port?: number; className?: string }> = ({
  port = 8000,
  className = ''
}) => {
  return <ServiceStatusIndicator port={port} showLabel={false} className={className} />;
};

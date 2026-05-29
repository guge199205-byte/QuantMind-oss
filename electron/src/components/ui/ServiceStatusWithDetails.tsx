import React from 'react';
import { useServiceStatus } from '../../hooks/useServiceStatus';

interface ServiceStatusWithDetailsProps {
  port: number;
}

export const ServiceStatusWithDetails: React.FC<ServiceStatusWithDetailsProps> = ({ port }) => {
  const { statuses } = useServiceStatus();
  const serviceStatus = statuses.get(`${port}`);

  if (!serviceStatus) {
    return (
      <div className="p-2 bg-gray-50 border border-gray-200 rounded">
        <p className="text-xs text-gray-600">正在检测服务状态...</p>
      </div>
    );
  }

  switch (serviceStatus.status) {
    case 'online':
      return (
        <div className="p-2 bg-green-50 border border-green-200 rounded">
          <p className="text-xs text-green-600">
            ✅ AI策略服务运行正常 (端口: {port}, 响应时间: {serviceStatus.responseTime}ms)
          </p>
        </div>
      );
    case 'offline':
      return (
        <div className="p-2 bg-red-50 border border-red-200 rounded">
          <p className="text-xs text-red-600">
            ⚠️ AI策略服务未启动，请确保服务运行在端口 {port} 上
            {serviceStatus.error && (
              <span className="block mt-1">错误信息: {serviceStatus.error}</span>
            )}
          </p>
        </div>
      );
    case 'checking':
      return (
        <div className="p-2 bg-yellow-50 border border-yellow-200 rounded">
          <p className="text-xs text-yellow-600">
            🔍 正在检测服务状态...
          </p>
        </div>
      );
    default:
      return (
        <div className="p-2 bg-gray-50 border border-gray-200 rounded">
          <p className="text-xs text-gray-600">
            未知服务状态
          </p>
        </div>
      );
  }
};

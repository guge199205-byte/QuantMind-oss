import { useEffect, useState } from 'react';
import { statusService, ServiceStatus } from '../services/statusService';

export const useServiceStatus = () => {
  const [statuses, setStatuses] = useState<Map<string, ServiceStatus>>(new Map());

  useEffect(() => {
    const updateStatuses = (newStatuses: Map<string, ServiceStatus>) => {
      setStatuses(new Map(newStatuses));
    };

    statusService.addListener(updateStatuses);

    return () => {
      statusService.removeListener(updateStatuses);
    };
  }, []);

  return {
    statuses,
    refresh: () => statusService.refresh(),
    getAIStrategyStatus: () => statusService.getAIStrategyStatus(),
    isAIStrategyOnline: () => statusService.isAIStrategyOnline(),
    summary: statusService.getSummary(),
  };
};

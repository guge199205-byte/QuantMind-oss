import { useQuery } from '@tanstack/react-query';
import { systemService, SystemCapabilities } from '../services/systemService';

/**
 * 获取系统能力与版本的 Hook
 * 使用 React Query 缓存，确保全局单例获取
 */
export const useCapabilities = () => {
  const { data: capabilities, isLoading, error } = useQuery<SystemCapabilities>({
    queryKey: ['system', 'capabilities'],
    queryFn: systemService.getCapabilities,
    staleTime: Infinity, // 系统版本在运行时通常不会改变
    retry: 3,
  });

  return {
    capabilities,
    isLoading,
    error,
    isOSS: capabilities?.edition === 'oss',
    isEnterprise: capabilities?.edition === 'enterprise',
    hasFeature: (feature: keyof SystemCapabilities['features']) => 
      capabilities?.features?.[feature] ?? true,
  };
};

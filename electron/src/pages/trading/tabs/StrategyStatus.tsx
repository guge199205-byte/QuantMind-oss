import React, { useEffect, useMemo, useState } from 'react';
import { Server, Box, Cpu, PieChart as PieChartIcon, CheckCircle2 } from 'lucide-react';
import { realTradingService, RealTradingStatus, AccountInfo } from '../../../services/realTradingService';
import { buildNormalizedHoldings, getPositionSummary } from '../utils/positionMetrics';
import PositionOverview from '../components/PositionOverview';

interface StrategyStatusProps {
    tenantId: string;
    userId: string;
    isActive: boolean;
}

const StrategyStatus: React.FC<StrategyStatusProps> = ({ tenantId, userId, isActive }) => {
    const [status, setStatus] = useState<RealTradingStatus | null>(null);
    const [accountInfo, setAccountInfo] = useState<AccountInfo | null>(null);
    const [_loading, setLoading] = useState(false);

    const fetchStatus = async () => {
        setLoading(true);
        try {
            const data = await realTradingService.getStatus(userId, tenantId);
            setStatus(data);

            const account = await realTradingService.getRuntimeAccount(userId, tenantId, data?.mode).catch(() => null);
            setAccountInfo(account);
        } catch (e) {
            // ignore
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (isActive) {
            fetchStatus();
            const interval = setInterval(fetchStatus, 5000);
            return () => clearInterval(interval);
        }
    }, [isActive, userId, tenantId]);

    const holdings = useMemo(() => buildNormalizedHoldings(accountInfo), [accountInfo]);
    const summary = useMemo(() => getPositionSummary(accountInfo), [accountInfo]);

    if (!isActive) return null;

    return (
        <div className="h-full flex flex-row p-6 space-x-6">
            {/* Left: K8s Monitor */}
            <div className="w-1/2 bg-gray-50 rounded-xl p-6 border border-gray-100 shadow-sm flex flex-col">
                <h3 className="text-lg font-bold text-gray-800 mb-6 flex items-center">
                    <Server className="mr-2 text-blue-600" size={20} />
                    K8s 运行监控
                </h3>

                {status && status.status === 'running' ? (
                    <div className="space-y-6 flex-1">
                        <div className="flex items-center justify-between bg-white p-5 rounded-lg border border-gray-200 shadow-sm">
                            <span className="text-gray-500 font-medium text-sm">Pod Name</span>
                            <span className="font-mono text-blue-600 bg-blue-50 px-2 py-1 rounded text-sm">{status.k8s_status?.name}</span>
                        </div>

                        <div className="grid grid-cols-2 gap-4">
                            <div className="bg-white p-5 rounded-lg border border-gray-200 shadow-sm flex flex-col items-center">
                                <div className="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center mb-2">
                                    <Box size={20} className="text-blue-600" />
                                </div>
                                <span className="text-3xl font-bold text-gray-800">{status.k8s_status?.replicas}</span>
                                <span className="text-xs text-gray-400 font-medium">Desired Replicas</span>
                            </div>
                            <div className="bg-white p-5 rounded-lg border border-gray-200 shadow-sm flex flex-col items-center">
                                <div className="w-10 h-10 rounded-full bg-green-100 flex items-center justify-center mb-2">
                                    <CheckCircle2 size={20} className="text-green-600" />
                                </div>
                                <span className="text-3xl font-bold text-gray-800">{status.k8s_status?.ready_replicas}</span>
                                <span className="text-xs text-gray-400 font-medium">Ready Replicas</span>
                            </div>
                        </div>

                        <div className="bg-white border border-gray-200 p-5 rounded-lg shadow-sm">
                            <h4 className="text-sm font-semibold text-gray-700 mb-4 flex items-center"><Cpu size={16} className="mr-2 text-gray-400" /> Resource Usage (Est.)</h4>
                            <div className="space-y-4">
                                <div className="space-y-1">
                                    <div className="flex justify-between text-xs font-medium text-gray-600">
                                        <span>CPU</span>
                                        <span>25%</span>
                                    </div>
                                    <div className="w-full bg-gray-100 rounded-full h-2">
                                        <div className="bg-blue-500 h-2 rounded-full" style={{ width: '25%' }}></div>
                                    </div>
                                </div>
                                <div className="space-y-1">
                                    <div className="flex justify-between text-xs font-medium text-gray-600">
                                        <span>Memory</span>
                                        <span>40%</span>
                                    </div>
                                    <div className="w-full bg-gray-100 rounded-full h-2">
                                        <div className="bg-purple-500 h-2 rounded-full" style={{ width: '40%' }}></div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                ) : (
                    <div className="flex-1 flex flex-col items-center justify-center text-gray-400">
                        <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mb-4">
                            <Server size={32} className="opacity-40" />
                        </div>
                        <p>暂无运行实例</p>
                    </div>
                )}
            </div>

            {/* Right: Portfolio */}
            <div className="w-1/2 bg-gray-50 rounded-xl p-6 border border-gray-100 shadow-sm flex flex-col">
                <h3 className="text-lg font-bold text-gray-800 mb-6 flex items-center">
                    <PieChartIcon className="mr-2 text-purple-600" size={20} />
                    持仓分布
                </h3>
                <PositionOverview holdings={holdings} summary={summary} variant="compact" className="flex-1 min-h-0" />
            </div>
        </div>
    );
};

export default StrategyStatus;

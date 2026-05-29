import React from 'react';
import { Wallet, Wifi, Activity } from 'lucide-react';

interface AccountInfo {
    total_asset: number;
    initial_equity: number;
    day_open_equity: number;
    month_open_equity: number;
    cash: number;
    market_value: number;
    frozen: number;
    daily_pnl: number;
    daily_pnl_percent: number;
    floating_pnl: number;
    floating_pnl_percent: number;
    total_pnl: number;
    total_pnl_percent: number;
    position_ratio: number;
    position_count: number;
}

interface TopBarProps {
    accountInfo?: AccountInfo;
    isConnected: boolean;
    strategyStatus: 'running' | 'starting' | 'stopped';
    tradingMode?: 'real' | 'simulation';
    runMode?: 'REAL' | 'SHADOW' | 'SIMULATION';
    orchestrationMode?: 'docker' | 'k8s';
}

const TopBar: React.FC<TopBarProps> = ({ accountInfo, isConnected, strategyStatus, tradingMode, runMode, orchestrationMode }) => {
    const formatMoney = (val: number | undefined) => {
        if (val === undefined || (!accountInfo && val === 0)) return '加载中...';
        return val.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    };

    const formatPercent = (val: number | undefined) => {
        if (val === undefined || (!accountInfo && val === 0)) return '--%';
        return `${(val * 100).toFixed(2)}%`;
    };

    const info = accountInfo;

    const getPnLColor = (val: number) => val > 0 ? 'text-red-600' : val < 0 ? 'text-green-600' : 'text-gray-900';
    const getPnLBg = (val: number) => val > 0 ? 'bg-red-50' : val < 0 ? 'bg-green-50' : 'bg-gray-50';

    const modeLabel = tradingMode === 'real' ? ' (实盘)' : (tradingMode === 'simulation' ? ' (模拟)' : '');
    const runModeLabel = runMode === 'SHADOW'
        ? '影子'
        : (runMode === 'REAL' ? '实盘' : (runMode === 'SIMULATION' ? '模拟' : '未启动'));
    const runModeTone = runMode === 'SHADOW' ? 'bg-violet-100 text-violet-800 border-violet-200'
        : (runMode === 'REAL' ? 'bg-blue-100 text-blue-800 border-blue-200'
            : (runMode === 'SIMULATION' ? 'bg-amber-100 text-amber-800 border-amber-200' : 'bg-gray-50 text-gray-500 border-gray-100'));
    const deployChannelLabel = runMode === 'SIMULATION'
        ? '沙箱'
        : (runMode === 'REAL' || runMode === 'SHADOW'
            ? (orchestrationMode === 'docker' ? 'Docker' : (orchestrationMode === 'k8s' ? 'Kubernetes' : '容器'))
            : '待部署');
    const deployChannelTone = runMode === 'SHADOW' ? 'bg-violet-50 text-violet-800 border-violet-200'
        : (runMode === 'REAL' ? 'bg-blue-50 text-blue-800 border-blue-200'
            : (runMode === 'SIMULATION' ? 'bg-amber-50 text-amber-800 border-amber-200' : 'bg-gray-50 text-gray-500 border-gray-100'));
    const strategyStatusLabel = strategyStatus === 'running' ? '策略运行中' : (strategyStatus === 'starting' ? '策略启动中' : '策略已停止');
    const strategyStatusColor = strategyStatus === 'running' ? 'text-blue-500' : (strategyStatus === 'starting' ? 'text-amber-500' : 'text-gray-300');

    const metrics = [
        {
            label: '总资产',
            hint: '账户当前总权益，含现金与持仓市值。',
            value: formatMoney(info?.total_asset),
            highlight: false,
        },
        {
            label: '初始权益',
            hint: '统一基线口径，对应 baseline.initial_equity。',
            value: formatMoney(info?.initial_equity),
            highlight: false,
        },
        {
            label: '可用资金',
            hint: '可用现金口径，优先使用账户快照 cash。',
            value: formatMoney(info?.cash),
            highlight: false,
        },
        {
            label: '持仓市值',
            hint: '当前持仓证券的实时市值汇总。',
            value: formatMoney(info?.market_value),
            highlight: false,
        },
        {
            label: '总盈亏',
            hint: '累计盈亏金额；副标签展示总收益率。',
            value: formatMoney(info?.total_pnl),
            subValue: info ? `${info.total_pnl > 0 ? '+' : ''}${(info.total_pnl_percent * 100).toFixed(2)}%` : undefined,
            subLabel: '总收益率',
            highlight: true,
            val: info?.total_pnl || 0,
        },
        {
            label: '今日盈亏',
            hint: '交易日口径盈亏；副标签展示日收益率。',
            value: formatMoney(info?.daily_pnl),
            subValue: info ? `${info.daily_pnl > 0 ? '+' : ''}${(info.daily_pnl_percent * 100).toFixed(2)}%` : undefined,
            subLabel: '日收益率',
            highlight: true,
            val: info?.daily_pnl || 0,
        },
        {
            label: '浮动盈亏',
            hint: '当前持仓未实现盈亏；副标签展示相对持仓市值占比。',
            value: formatMoney(info?.floating_pnl),
            subValue: info ? `${info.floating_pnl > 0 ? '+' : ''}${(info.floating_pnl_percent * 100).toFixed(2)}%` : undefined,
            subLabel: '持仓收益率',
            highlight: true,
            val: info?.floating_pnl || 0,
        },
        {
            label: '持仓数量',
            hint: '当前持仓标的数量；副标签展示仓位占比。',
            value: (info?.position_count || 0).toString(),
            subValue: info ? formatPercent(info.position_ratio) : undefined,
            subLabel: '仓位占比',
            highlight: false,
        },
    ];

    return (
        <div className="h-full flex flex-col p-6">
            {/* Header with Status */}
            <div className="flex justify-between items-center mb-5 pb-3.5 border-b border-gray-100 gap-4">
                <div className="flex items-center gap-2.5 min-w-0">
                    <div className="p-1.5 bg-blue-50 rounded-xl shrink-0">
                        <Wallet className="text-blue-600" size={18} />
                    </div>
                    <h2 className="text-lg font-bold text-gray-800 whitespace-nowrap">账户资产概览{modeLabel}</h2>
                    <div className="flex flex-nowrap items-center gap-1 shrink-0">
                        <span className={`px-2 py-0.5 rounded-full text-[10px] leading-4 font-bold border whitespace-nowrap ${runModeTone}`}>
                            当前运行模式: {runModeLabel}
                        </span>
                        <span className={`px-2 py-0.5 rounded-full text-[10px] leading-4 font-bold border whitespace-nowrap ${deployChannelTone}`}>
                            部署通道: {deployChannelLabel}
                        </span>
                    </div>
                </div>
                <div className="flex items-center gap-3 shrink-0">
                    <div className="flex items-center gap-1.5 px-2.5 py-1 bg-gray-50 rounded-full">
                        <Wifi size={14} className={isConnected ? 'text-green-500' : 'text-red-400'} />
                        <span className="text-xs font-medium text-gray-600">{isConnected ? '在线' : '离线'}</span>
                    </div>
                    <div className="flex items-center gap-1.5 px-2.5 py-1 bg-gray-50 rounded-full">
                        <Activity size={14} className={strategyStatusColor} />
                        <span className="text-xs font-medium text-gray-600">{strategyStatusLabel}</span>
                    </div>

                </div>
            </div>

            {/* Metrics Grid - 4x2 紧凑居中布局 */}
            <div className="flex-1 grid grid-cols-4 grid-rows-2 gap-4">
                {metrics.map((m, idx) => (
                    <div key={idx} title={m.hint} className="flex flex-col justify-center items-center bg-gray-50 rounded-2xl p-4 border border-gray-100 transition-shadow hover:shadow-md">
                        <span className="text-xs font-medium text-gray-500 mb-2">{m.label}</span>
                        <div className="flex flex-col items-center">
                            <span className={`text-2xl font-bold ${m.highlight ? getPnLColor(m.val!) : 'text-gray-900'}`}>
                                {m.highlight && m.val! > 0 ? '+' : ''}{m.value}
                            </span>
                            {m.subValue && (
                                <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-lg mt-1 ${m.highlight ? `${getPnLBg(m.val!)} ${getPnLColor(m.val!)}` : 'bg-gray-100 text-gray-600'}`}>
                                    {m.subValue}
                                </span>
                            )}
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
};

export default TopBar;

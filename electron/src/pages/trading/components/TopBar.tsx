import React, { useState } from 'react';
import { Wallet, Wifi, Activity, ChevronDown, ChevronUp } from 'lucide-react';

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
    const [expanded, setExpanded] = useState(false);

    const formatMoney = (val: number | undefined) => {
        if (val === undefined || (!accountInfo && val === 0)) return '加载中...';
        return val.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    };

    const formatPercent = (val: number | undefined) => {
        if (val === undefined || (!accountInfo && val === 0)) return '--%';
        return `${(val * 100).toFixed(2)}%`;
    };

    const info = accountInfo;

    const getPnLColor = (val: number) => val > 0 ? 'text-red-600' : val < 0 ? 'text-green-600' : 'text-gray-700';
    const getPnLBg = (val: number) => val > 0 ? 'bg-red-50' : val < 0 ? 'bg-green-50' : 'bg-gray-50';

    const modeLabel = tradingMode === 'real' ? ' (实盘)' : (tradingMode === 'simulation' ? ' (模拟)' : '');
    const runModeLabel = runMode === 'SHADOW'
        ? '影子'
        : (runMode === 'REAL' ? '实盘' : (runMode === 'SIMULATION' ? '模拟' : '未启动'));
    const runModeTone = runMode === 'SHADOW' ? 'bg-violet-100 text-violet-700 border-violet-200'
        : (runMode === 'REAL' ? 'bg-blue-100 text-blue-700 border-blue-200'
            : (runMode === 'SIMULATION' ? 'bg-amber-100 text-amber-700 border-amber-200' : 'bg-gray-100 text-gray-500 border-gray-200'));
    const deployChannelLabel = runMode === 'SIMULATION'
        ? '沙箱'
        : (runMode === 'REAL' || runMode === 'SHADOW'
            ? (orchestrationMode === 'docker' ? 'Docker' : (orchestrationMode === 'k8s' ? 'K8s' : '容器'))
            : '待部署');
    const deployChannelTone = runMode === 'SHADOW' ? 'bg-violet-50 text-violet-700 border-violet-200'
        : (runMode === 'REAL' ? 'bg-blue-50 text-blue-700 border-blue-200'
            : (runMode === 'SIMULATION' ? 'bg-amber-50 text-amber-700 border-amber-200' : 'bg-gray-50 text-gray-500 border-gray-200'));
    const strategyStatusLabel = strategyStatus === 'running' ? '运行中' : (strategyStatus === 'starting' ? '启动中' : '已停止');
    const strategyStatusColor = strategyStatus === 'running' ? 'text-blue-500' : (strategyStatus === 'starting' ? 'text-amber-500' : 'text-gray-400');

    const metrics = [
        { label: '总资产', value: formatMoney(info?.total_asset), highlight: false },
        { label: '初始权益', value: formatMoney(info?.initial_equity), highlight: false },
        { label: '可用资金', value: formatMoney(info?.cash), highlight: false },
        { label: '持仓市值', value: formatMoney(info?.market_value), highlight: false },
        {
            label: '总盈亏', value: formatMoney(info?.total_pnl), highlight: true, val: info?.total_pnl || 0,
            subValue: info ? `${info.total_pnl > 0 ? '+' : ''}${(info.total_pnl_percent * 100).toFixed(2)}%` : undefined,
        },
        {
            label: '今日盈亏', value: formatMoney(info?.daily_pnl), highlight: true, val: info?.daily_pnl || 0,
            subValue: info ? `${info.daily_pnl > 0 ? '+' : ''}${(info.daily_pnl_percent * 100).toFixed(2)}%` : undefined,
        },
        {
            label: '浮动盈亏', value: formatMoney(info?.floating_pnl), highlight: true, val: info?.floating_pnl || 0,
            subValue: info ? `${info.floating_pnl > 0 ? '+' : ''}${(info.floating_pnl_percent * 100).toFixed(2)}%` : undefined,
        },
        {
            label: '持仓数量', value: (info?.position_count || 0).toString(), highlight: false,
            subValue: info ? formatPercent(info.position_ratio) : undefined,
        },
    ];

    return (
        <div className="flex flex-col h-full px-4 py-2.5">
            {/* Single-line header: title + status + expand toggle */}
            <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2 min-w-0">
                    <div className="p-1 bg-blue-50 rounded-lg shrink-0">
                        <Wallet className="text-blue-600" size={14} />
                    </div>
                    <span className="text-sm font-bold text-gray-800 whitespace-nowrap">资产概览{modeLabel}</span>
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold border whitespace-nowrap ${runModeTone}`}>
                        {runModeLabel}
                    </span>
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold border whitespace-nowrap ${deployChannelTone}`}>
                        {deployChannelLabel}
                    </span>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                    <div className="flex items-center gap-1 px-1.5 py-0.5 bg-gray-50 rounded-full">
                        <Wifi size={11} className={isConnected ? 'text-green-500' : 'text-red-400'} />
                        <span className="text-[10px] font-medium text-gray-500">{isConnected ? '在线' : '离线'}</span>
                    </div>
                    <div className="flex items-center gap-1 px-1.5 py-0.5 bg-gray-50 rounded-full">
                        <Activity size={11} className={strategyStatusColor} />
                        <span className="text-[10px] font-medium text-gray-500">{strategyStatusLabel}</span>
                    </div>
                    <button
                        onClick={() => setExpanded(!expanded)}
                        className="flex items-center gap-0.5 px-1.5 py-0.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded transition-colors"
                        title={expanded ? '收起详情' : '展开详情'}
                    >
                        {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                    </button>
                </div>
            </div>

            {expanded ? (
                /* Expanded: compact 4x2 grid */
                <div className="flex-1 grid grid-cols-4 grid-rows-2 gap-2 mt-2">
                    {metrics.map((m, idx) => (
                        <div key={idx} className="flex flex-col justify-center items-center bg-gray-50 rounded-lg px-2 py-1.5 border border-gray-100 hover:shadow-sm transition-shadow">
                            <span className="text-[10px] font-medium text-gray-400 mb-0.5">{m.label}</span>
                            <span className={`text-sm font-bold ${m.highlight ? getPnLColor(m.val!) : 'text-gray-800'}`}>
                                {m.highlight && m.val! > 0 ? '+' : ''}{m.value}
                            </span>
                            {m.subValue && (
                                <span className={`text-[9px] font-semibold px-1 py-0 rounded mt-0.5 ${m.highlight ? `${getPnLBg(m.val!)} ${getPnLColor(m.val!)}` : 'bg-gray-100 text-gray-500'}`}>
                                    {m.subValue}
                                </span>
                            )}
                        </div>
                    ))}
                </div>
            ) : (
                /* Collapsed: single row key metrics */
                <div className="flex-1 flex items-center gap-4 mt-1">
                    {[
                        { label: '总资产', value: formatMoney(info?.total_asset) },
                        { label: '可用', value: formatMoney(info?.cash) },
                        {
                            label: '今日',
                            value: formatMoney(info?.daily_pnl),
                            color: getPnLColor(info?.daily_pnl || 0),
                            suffix: info ? `${info.daily_pnl > 0 ? '+' : ''}${(info.daily_pnl_percent * 100).toFixed(2)}%` : undefined,
                        },
                        {
                            label: '总盈亏',
                            value: formatMoney(info?.total_pnl),
                            color: getPnLColor(info?.total_pnl || 0),
                            suffix: info ? `${info.total_pnl > 0 ? '+' : ''}${(info.total_pnl_percent * 100).toFixed(2)}%` : undefined,
                        },
                        { label: '持仓', value: `${info?.position_count || 0}只` },
                    ].map((m, idx) => (
                        <div key={idx} className="flex items-baseline gap-1.5">
                            <span className="text-[10px] text-gray-400">{m.label}</span>
                            <span className={`text-sm font-bold ${m.color || 'text-gray-800'}`}>{m.value}</span>
                            {m.suffix && (
                                <span className={`text-[10px] font-semibold ${m.color || 'text-gray-500'}`}>{m.suffix}</span>
                            )}
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
};

export default TopBar;

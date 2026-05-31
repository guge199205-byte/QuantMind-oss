import React, { useEffect, useMemo, useState, useRef, useCallback } from 'react';
import { Alert, Button, Card, Col, Descriptions, Input, Row, Space, Spin, Statistic, Table, Tag, message, Typography, Progress, Divider, Tooltip, Empty } from 'antd';
import {
    DatabaseOutlined,
    ReloadOutlined,
    CloudSyncOutlined,
    CheckCircleFilled,
    WarningFilled,
    FileTextOutlined,
    ThunderboltOutlined,
    CompassOutlined,
    LineChartOutlined,
    InfoCircleOutlined,
    CodeOutlined,
    SafetyCertificateOutlined,
    UserOutlined,
    SyncOutlined,
    CloudDownloadOutlined,
    GlobalOutlined,
    StockOutlined,
    FundOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';
import { adminService } from '../services/adminService';
import {
    AdminFeatureSnapshotsOlderSample,
    AdminFeatureSnapshotsInvalidSample,
    AdminDataStatusResult,
    AdminOfficialDataUpdateSyncResult,
} from '../types';

// Alpha Agent 市场配置
const MARKET_CONFIG: Record<string, { label: string; icon: React.ReactNode; color: string; gradient: string }> = {
    a_share: { label: 'A股', icon: <StockOutlined />, color: '#ef4444', gradient: 'from-red-500 to-orange-500' },
    crypto: { label: '加密货币', icon: <FundOutlined />, color: '#f59e0b', gradient: 'from-amber-500 to-yellow-500' },
    hong_kong: { label: '港股', icon: <GlobalOutlined />, color: '#3b82f6', gradient: 'from-blue-500 to-cyan-500' },
    us_stock: { label: '美股', icon: <LineChartOutlined />, color: '#10b981', gradient: 'from-emerald-500 to-teal-500' },
};

const { Title, Text, Paragraph } = Typography;

export const AdminDataManagement: React.FC = () => {
    const [loading, setLoading] = useState(false);
    const [data, setData] = useState<AdminDataStatusResult | null>(null);
    const [syncLoading, setSyncLoading] = useState(false);
    const [syncResult, setSyncResult] = useState<AdminOfficialDataUpdateSyncResult | null>(null);
    const [dailySyncLoading, setDailySyncLoading] = useState(false);
    const [syncStatus, setSyncStatus] = useState<any>(null);
    const [syncStatusLoading, setSyncStatusLoading] = useState(false);

    const loadDataStatus = async (refresh = false) => {
        setLoading(true);
        try {
            const resp = await adminService.getDataStatus(refresh);
            setData(resp);
            if (refresh) {
                message.success(resp.message || '后台扫描任务已启动，请稍后刷新查看最新状态');
            }
        } catch (err: unknown) {
            const msg = err instanceof Error ? err.message : '未知错误';
            message.error(`数据状态同步失败: ${msg}`);
        } finally {
            setLoading(false);
        }
    };

    const initialRefreshRef = useRef(false);

    const loadSyncStatus = useCallback(async () => {
        setSyncStatusLoading(true);
        try {
            const resp = await adminService.getSyncStatus();
            setSyncStatus(resp?.data || resp);
        } catch {
            // silent
        } finally {
            setSyncStatusLoading(false);
        }
    }, []);

    useEffect(() => {
        if (!initialRefreshRef.current) {
            loadDataStatus(true);
            loadSyncStatus();
            initialRefreshRef.current = true;
        }
    }, []);

    const qlib = data?.qlib_data;
    const snapshots = data?.feature_snapshots;
    const checkedAt = data?.checked_at ? dayjs(data.checked_at).format('HH:mm:ss') : '—';
    const olderSamples = snapshots?.topn_samples?.older_samples || [];
    const invalidSamples = snapshots?.topn_samples?.invalid_samples || [];
    const sampleSize = snapshots?.topn_samples?.sample_size || 20;

    const coverageRate = useMemo(() => {
        const c = snapshots?.latest_date_coverage;
        if (!c) return 0;
        const total = c.at_target_count + c.older_count + c.invalid_count;
        if (total <= 0) return 0;
        return Math.round((c.at_target_count / total) * 10000) / 100;
    }, [snapshots]);

    const olderColumns = [
        {
            title: '股票代码',
            dataIndex: 'symbol',
            key: 'symbol',
            width: 100,
            render: (v: string) => <span className="font-mono font-black text-indigo-600">{v}</span>,
        },
        {
            title: '最新日期',
            dataIndex: 'last_date',
            key: 'last_date',
            width: 120,
            render: (v: string) => <Text className="font-mono text-slate-500">{v}</Text>
        },
        {
            title: '滞后天数',
            dataIndex: 'lag_days',
            key: 'lag_days',
            width: 100,
            align: 'right' as const,
            render: (v: number) => (
                <Tag color={v > 60 ? '#f43f5e' : v > 10 ? '#f59e0b' : '#10b981'} className="m-0 border-none font-bold rounded-lg px-2">
                    {v}天
                </Tag>
            ),
        },
    ];

    const invalidColumns = [
        {
            title: '股票代码',
            dataIndex: 'symbol',
            key: 'symbol',
            width: 100,
            render: (v: string) => <span className="font-mono font-black text-rose-600">{v}</span>,
        },
        {
            title: '原因',
            dataIndex: 'reason',
            key: 'reason',
            render: (v: string) => <Tag color="error" className="m-0 border-none rounded-md px-2 text-[11px] font-bold uppercase tracking-tight">{v}</Tag>,
        },
        {
            title: '文件路径',
            dataIndex: 'file',
            key: 'file',
            ellipsis: true as const,
            render: (v?: string) => <Text className="text-slate-400 font-mono text-[10px] italic">{v || '—'}</Text>,
        },
    ];

    const handleUpdateFeatureParquet = async (rebuild = false) => {
        setParquetLoading(true);
        setParquetResult(null);
        try {
            const resp = await adminService.updateFeatureParquet(rebuild);
            setParquetResult(resp);
            if (resp.success) {
                message.success(rebuild ? '特征快照已全量重建' : '特征快照已更新');
                await loadDataStatus(false);
            } else {
                message.error('特征更新失败，请查看执行日志');
            }
        } catch (err: unknown) {
            const msg = err instanceof Error ? err.message : '未知错误';
            message.error(`更新失败: ${msg}`);
        } finally {
            setParquetLoading(false);
        }
    };

    const handleSyncOfficialData = async () => {
        setSyncLoading(true);
        try {
            const resp = await adminService.syncOfficialDataUpdate({
                apiBaseUrl: '',
                accessKey: '',
                secretKey: '',
            });
            setSyncResult(resp);
            if (resp.success) {
                message.success('数据全自动增量同步已启动');
                await loadDataStatus(true);
            } else {
                message.error(resp.error || '同步任务执行异常');
            }
        } catch (err: unknown) {
            const msg = err instanceof Error ? err.message : '未知网络错误';
            message.error(`同步失败: ${msg}`);
        } finally {
            setSyncLoading(false);
        }
    };

    const [syncTaskId, setSyncTaskId] = useState<string | null>(null);
    const [syncTaskProgress, setSyncTaskProgress] = useState<string>('');
    const [syncStepProgress, setSyncStepProgress] = useState<{ step: string; detail: string; pct: number; current: number; total: number } | null>(null);
    const [parquetLoading, setParquetLoading] = useState(false);
    const [parquetResult, setParquetResult] = useState<any>(null);

    // Alpha Agent 市场数据状态
    const [marketsData, setMarketsData] = useState<any[]>([]);
    const [marketsLoading, setMarketsLoading] = useState(false);
    const [selectedMarket, setSelectedMarket] = useState<string>('a_share');
    const [marketSyncing, setMarketSyncing] = useState<string | null>(null);

    const loadMarketsData = useCallback(async () => {
        setMarketsLoading(true);
        try {
            const resp = await adminService.getAlphaAgentMarkets();
            if (resp?.success && resp.data?.markets) {
                setMarketsData(resp.data.markets);
            }
        } catch {
            // silent
        } finally {
            setMarketsLoading(false);
        }
    }, []);

    const handleSyncMarket = async (marketId: string, force = false) => {
        setMarketSyncing(marketId);
        try {
            const resp = await adminService.syncAlphaAgentMarket(marketId);
            if (resp?.success) {
                const d = resp.data;
                if (d.status === 'already_ready') {
                    message.info(d.message || `${marketId} 数据已就绪`);
                } else if (d.status === 'completed') {
                    message.success(d.message || `${marketId} 数据同步完成`);
                } else if (d.status === 'skipped') {
                    message.warning(d.message || `${marketId} 已跳过`);
                }
                await loadMarketsData();
            } else {
                message.error('同步失败');
            }
        } catch (err: any) {
            message.error(`同步失败: ${err?.message || '未知错误'}`);
        } finally {
            setMarketSyncing(null);
        }
    };

    useEffect(() => {
        loadMarketsData();
    }, [loadMarketsData]);

    const handleDailySync = async (incremental = true) => {
        setDailySyncLoading(true);
        setSyncTaskProgress('提交任务...');
        setSyncStepProgress(null);
        try {
            const resp = await adminService.triggerDailySync({ incremental, calibrate: true });
            if (resp?.success && resp.data?.task_id) {
                const taskId = resp.data.task_id;
                setSyncTaskId(taskId);
                setSyncTaskProgress('任务已提交，等待执行...');
                message.info(`同步任务已提交 (${taskId.slice(0, 8)}...)，后台执行中`);

                // 轮询任务状态 + 步骤进度
                const pollInterval = setInterval(async () => {
                    try {
                        // 同时查 Celery 任务状态和步骤进度
                        const [statusResp, progressResp] = await Promise.all([
                            adminService.getDailySyncTaskStatus(taskId),
                            adminService.getSyncProgress(),
                        ]);

                        // 更新步骤进度
                        const prog = progressResp?.data;
                        if (prog && prog.step !== 'idle') {
                            setSyncStepProgress(prog);
                        }

                        const d = statusResp?.data;
                        if (!d) return;

                        if (d.status === 'SUCCESS') {
                            clearInterval(pollInterval);
                            const r = d.result || {};
                            if (r.status === 'skipped') {
                                message.warning(r.reason || '已有同步任务在运行');
                            } else {
                                message.success(
                                    `同步完成: investment_data=${r.investment_data_synced || 0}, baostock=${r.baostock_synced || 0}, akshare=${r.akshare_synced || 0}, eltdx=${r.eltdx_synced || 0}`
                                );
                            }
                            setDailySyncLoading(false);
                            setSyncTaskId(null);
                            setSyncTaskProgress('');
                            setSyncStepProgress(null);
                            await loadSyncStatus();
                            await loadDataStatus(false);
                        } else if (d.status === 'FAILURE') {
                            clearInterval(pollInterval);
                            const errMsg = d.error && d.error !== `engine.tasks.daily_data_sync`
                                ? d.error
                                : '任务执行异常，请查看后端日志';
                            message.error(`同步失败: ${errMsg}`);
                            setDailySyncLoading(false);
                            setSyncTaskId(null);
                            setSyncTaskProgress('');
                            setSyncStepProgress(null);
                        } else {
                            // PENDING / STARTED
                            setSyncTaskProgress(d.status === 'STARTED' ? '同步执行中...' : '等待队列...');
                        }
                    } catch {
                        // polling error, continue
                    }
                }, 3000);

                // 超时保护: 30 分钟后停止轮询
                setTimeout(() => {
                    clearInterval(pollInterval);
                    if (dailySyncLoading) {
                        message.warning('同步任务超时，请手动检查状态');
                        setDailySyncLoading(false);
                        setSyncTaskId(null);
                        setSyncTaskProgress('');
                        setSyncStepProgress(null);
                    }
                }, 30 * 60 * 1000);
            } else {
                message.error('任务提交失败');
                setDailySyncLoading(false);
            }
        } catch (err: unknown) {
            const msg = err instanceof Error ? err.message : '未知错误';
            message.error(`提交失败: ${msg}`);
            setDailySyncLoading(false);
            setSyncTaskProgress('');
            setSyncStepProgress(null);
        }
    };

    return (
        <div className="pb-24 space-y-10 animate-in fade-in slide-in-from-bottom-4 duration-700">
            {/* Header Section */}
            <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-6">
                <div>
                    <Title level={1} className="!m-0 !font-black !text-4xl !tracking-tighter !text-slate-900 uppercase">
                        数据管理
                    </Title>
                    <div className="flex items-center mt-2 space-x-3">
                        <Tag className="rounded-full bg-slate-100 border-none text-slate-500 font-bold px-3">
                            节点: QUANT-OSS-01
                        </Tag>
                        <Text className="text-slate-400 font-medium text-sm flex items-center">
                            <InfoCircleOutlined className="mr-1.5" />
                            最后扫描时间: <span className="text-indigo-500 font-bold ml-1">{checkedAt}</span>
                        </Text>
                    </div>
                </div>
                <Space size="middle">
                    <Button
                        type="primary"
                        icon={<ThunderboltOutlined />}
                        className="rounded-2xl h-11 px-8 bg-indigo-600 border-none font-bold shadow-lg shadow-indigo-100"
                        loading={loading}
                        onClick={() => loadDataStatus(true)}
                    >
                        强制深度扫描
                    </Button>
                    <Button
                        icon={<ReloadOutlined />}
                        className="rounded-2xl h-11 px-8 border-slate-200 text-slate-600 font-bold hover:bg-slate-50 transition-all"
                        loading={loading}
                        onClick={() => loadDataStatus(false)}
                    >
                        刷新
                    </Button>
                </Space>
            </div>

            {/* Alpha Agent 市场数据管理 */}
            <Card
                className="rounded-[2.5rem] border-none shadow-2xl shadow-slate-200/30"
                styles={{ body: { padding: '32px' } }}
            >
                <div className="flex items-center justify-between mb-6">
                    <div className="flex items-center space-x-3">
                        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center">
                            <GlobalOutlined className="text-white text-xl" />
                        </div>
                        <div>
                            <span className="text-slate-800 font-black text-xl uppercase tracking-tight block">多市场数据</span>
                            <span className="text-[10px] text-slate-400 font-bold uppercase tracking-widest">Alpha Agent 因子挖掘数据源</span>
                        </div>
                    </div>
                    <Button
                        type="text"
                        size="small"
                        icon={<ReloadOutlined spin={marketsLoading} />}
                        onClick={loadMarketsData}
                        className="text-slate-400"
                    />
                </div>

                {/* 市场标签选择器 */}
                <div className="flex flex-wrap gap-3 mb-6">
                    {marketsData.map((m) => {
                        const cfg = MARKET_CONFIG[m.market_id] || { label: m.market_name, icon: <DatabaseOutlined />, color: '#6366f1', gradient: 'from-indigo-500 to-purple-500' };
                        const isActive = selectedMarket === m.market_id;
                        return (
                            <button
                                key={m.market_id}
                                onClick={() => setSelectedMarket(m.market_id)}
                                className={`
                                    relative flex items-center gap-2.5 px-5 py-3 rounded-2xl font-bold text-sm transition-all duration-300 cursor-pointer border-none outline-none
                                    ${isActive
                                        ? `bg-gradient-to-r ${cfg.gradient} text-white shadow-lg scale-[1.02]`
                                        : 'bg-slate-50 text-slate-600 hover:bg-slate-100 hover:scale-[1.01]'
                                    }
                                `}
                            >
                                <span className="text-base">{cfg.icon}</span>
                                <span className="tracking-tight">{cfg.label}</span>
                                {m.data_ready ? (
                                    <span className={`w-2 h-2 rounded-full ${isActive ? 'bg-white/80' : 'bg-emerald-400'} animate-pulse`} />
                                ) : (
                                    <span className={`w-2 h-2 rounded-full ${isActive ? 'bg-white/40' : 'bg-slate-300'}`} />
                                )}
                            </button>
                        );
                    })}
                </div>

                {/* 选中市场的详情 */}
                {(() => {
                    const m = marketsData.find(x => x.market_id === selectedMarket);
                    if (!m) return <Empty description="暂无市场数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />;
                    const cfg = MARKET_CONFIG[m.market_id] || { label: m.market_name, color: '#6366f1', gradient: 'from-indigo-500 to-purple-500' };
                    const h5 = m.h5_info;
                    const qlib = m.qlib_info;

                    return (
                        <div className="space-y-5">
                            {/* 状态行 */}
                            <div className="flex items-center justify-between p-5 rounded-2xl bg-slate-50 border border-slate-100">
                                <div className="flex items-center gap-4">
                                    <div className={`w-12 h-12 rounded-2xl bg-gradient-to-br ${cfg.gradient} flex items-center justify-center text-white text-xl shadow-lg`}>
                                        {MARKET_CONFIG[m.market_id]?.icon || <DatabaseOutlined />}
                                    </div>
                                    <div>
                                        <div className="flex items-center gap-2">
                                            <span className="font-black text-lg text-slate-800">{m.market_name}</span>
                                            {m.data_ready ? (
                                                <Tag className="m-0 border-none bg-emerald-50 text-emerald-600 font-bold rounded-lg text-[10px]">
                                                    <CheckCircleFilled className="mr-1" /> 已就绪
                                                </Tag>
                                            ) : (
                                                <Tag className="m-0 border-none bg-amber-50 text-amber-600 font-bold rounded-lg text-[10px]">
                                                    <WarningFilled className="mr-1" /> 未就绪
                                                </Tag>
                                            )}
                                        </div>
                                        <span className="text-xs text-slate-400">{m.description}</span>
                                    </div>
                                </div>
                                <Space>
                                    <Button
                                        type="primary"
                                        icon={<SyncOutlined />}
                                        loading={marketSyncing === m.market_id}
                                        onClick={() => handleSyncMarket(m.market_id, m.data_ready)}
                                        className={`rounded-xl h-10 px-6 font-bold border-none shadow-md ${m.data_ready ? 'bg-slate-600 hover:bg-slate-700' : `bg-gradient-to-r ${cfg.gradient} hover:opacity-90`}`}
                                    >
                                        {m.data_ready ? '重新同步' : '开始同步'}
                                    </Button>
                                </Space>
                            </div>

                            {/* 数据详情网格 */}
                            {h5 ? (
                                <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                                    {[
                                        { label: '标的数量', value: `${h5.symbols} 只`, color: 'text-indigo-600' },
                                        { label: '数据行数', value: h5.rows.toLocaleString(), color: 'text-slate-800' },
                                        { label: '起始日期', value: h5.start_date, color: 'text-slate-600' },
                                        { label: '截止日期', value: h5.end_date, color: 'text-emerald-600' },
                                        { label: '文件大小', value: `${h5.file_size_mb} MB`, color: 'text-amber-600' },
                                    ].map((item, i) => (
                                        <div key={i} className="p-4 rounded-2xl bg-white border border-slate-100 shadow-sm">
                                            <Text className="text-[9px] font-bold text-slate-400 uppercase tracking-widest block mb-1">{item.label}</Text>
                                            <Text className={`font-black text-base tracking-tight ${item.color}`}>{item.value}</Text>
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <div className="p-6 rounded-2xl bg-amber-50 border border-amber-100 text-center">
                                    <WarningFilled className="text-amber-500 text-lg mr-2" />
                                    <Text className="text-amber-700 font-bold text-sm">数据文件不存在，请点击「开始同步」下载数据</Text>
                                </div>
                            )}

                            {/* Qlib 信息 */}
                            {qlib && (
                                <div className="flex items-center gap-6 px-5 py-3 rounded-xl bg-indigo-50/50 border border-indigo-100">
                                    <div className="flex items-center gap-2">
                                        <DatabaseOutlined className="text-indigo-400 text-xs" />
                                        <Text className="text-[10px] font-bold text-indigo-500 uppercase">Qlib</Text>
                                    </div>
                                    <Text className="text-xs text-slate-600">
                                        日历: <span className="font-bold">{qlib.calendar_files?.join(', ') || '—'}</span>
                                    </Text>
                                    <Text className="text-xs text-slate-600">
                                        特征目录: <span className="font-bold text-indigo-600">{qlib.feature_dirs}</span> 个
                                    </Text>
                                </div>
                            )}
                        </div>
                    );
                })()}
            </Card>

            {/* Quick Stats Grid */}
            <Row gutter={[24, 24]}>
                <Col xs={24} sm={12} lg={6}>
                    <Card className="rounded-[2rem] border-none shadow-xl shadow-slate-200/40 bg-white group overflow-hidden">
                        <div className="absolute top-0 right-0 w-24 h-24 bg-blue-500 opacity-[0.03] rounded-bl-[4rem]" />
                        <Statistic 
                            title={<span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Qlib 日历最后日期</span>} 
                            value={qlib?.calendar_last_date || '—'} 
                            valueStyle={{ fontWeight: 900, letterSpacing: '-0.02em', color: '#1e293b' }}
                            prefix={<CompassOutlined className="text-blue-500 mr-2" />}
                        />
                    </Card>
                </Col>
                <Col xs={24} sm={12} lg={6}>
                    <Card className="rounded-[2rem] border-none shadow-xl shadow-slate-200/40 bg-white group overflow-hidden">
                        <div className="absolute top-0 right-0 w-24 h-24 bg-indigo-500 opacity-[0.03] rounded-bl-[4rem]" />
                        <Statistic 
                            title={<span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">快照最新日期</span>} 
                            value={snapshots?.max_date || '—'} 
                            valueStyle={{ fontWeight: 900, letterSpacing: '-0.02em', color: '#1e293b' }}
                            prefix={<LineChartOutlined className="text-indigo-500 mr-2" />}
                        />
                    </Card>
                </Col>
                <Col xs={24} sm={12} lg={6}>
                    <Card className="rounded-[2rem] border-none shadow-xl shadow-slate-200/40 bg-white group overflow-hidden">
                        <div className="absolute top-0 right-0 w-24 h-24 bg-emerald-500 opacity-[0.03] rounded-bl-[4rem]" />
                        <Statistic 
                            title={<span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Parquet 文件总数</span>} 
                            value={snapshots?.file_count ?? 0} 
                            suffix="个"
                            valueStyle={{ fontWeight: 900, letterSpacing: '-0.02em', color: '#1e293b' }}
                            prefix={<DatabaseOutlined className="text-emerald-500 mr-2" />}
                        />
                    </Card>
                </Col>
                <Col xs={24} sm={12} lg={6}>
                    <Card className="rounded-[2rem] border-none shadow-xl shadow-slate-200/40 bg-white group overflow-hidden">
                        <div className="flex flex-col">
                            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2">覆盖率</span>
                            <div className="flex items-center space-x-4">
                                <Progress 
                                    type="circle" 
                                    percent={coverageRate} 
                                    size={48} 
                                    strokeWidth={12}
                                    strokeColor={{ '0%': '#6366f1', '100%': '#10b981' }}
                                    format={() => <span className="text-[10px] font-black text-slate-700">{Math.round(coverageRate)}%</span>}
                                />
                                <div>
                                    <div className="text-2xl font-black text-slate-800 tracking-tight">{coverageRate}%</div>
                                    <div className="text-[10px] font-bold text-emerald-500">良好</div>
                                </div>
                            </div>
                        </div>
                    </Card>
                </Col>
            </Row>

            {/* Main Content Area */}
            <Row gutter={[32, 32]}>
                <Col span={24} lg={15} className="space-y-8">
                    {/* Qlib Section */}
                    <Card
                        title={
                            <div className="flex items-center space-x-3 py-1">
                                <div className="w-8 h-8 rounded-lg bg-blue-50 flex items-center justify-center text-blue-600">
                                    <DatabaseOutlined />
                                </div>
                                <span className="font-black text-slate-800 tracking-tight text-lg uppercase">Qlib 基础设施详情</span>
                            </div>
                        }
                        className="rounded-[2.5rem] border-none shadow-2xl shadow-slate-200/30"
                        styles={{ body: { padding: '32px' } }}
                    >
                        {!qlib?.exists ? (
                            <Alert
                                type="error"
                                showIcon
                                message={<span className="font-bold">Qlib 目录不存在</span>}
                                description={<span className="text-xs italic opacity-70">{qlib?.qlib_dir || '路径未定义'}</span>}
                                className="rounded-2xl"
                            />
                        ) : (
                            <div className="grid grid-cols-2 md:grid-cols-3 gap-y-8 gap-x-12">
                                {[
                                    { label: 'Qlib 路径', value: qlib.qlib_dir, span: 3, full: true },
                                    { label: '日历总天数', value: qlib.calendar_total_days },
                                    { label: '日历区间', value: `${qlib.calendar_start_date} → ${qlib.calendar_last_date}`, span: 2 },
                                    { label: '标的总数', value: qlib.instruments?.total, highlight: true },
                                    { label: '特征目录数', value: qlib.feature_dirs_total },
                                    { label: '交易所分布', value: `SH: ${qlib.instruments?.sh} | SZ: ${qlib.instruments?.sz} | BJ: ${qlib.instruments?.bj}`, span: 3, italic: true }
                                ].map((item, i) => (
                                    <div key={i} className={`flex flex-col space-y-1 ${item.span === 3 ? 'col-span-full' : item.span === 2 ? 'col-span-2' : ''}`}>
                                        <Text className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">{item.label}</Text>
                                        <Text className={`text-slate-800 ${item.full ? 'font-mono text-xs break-all' : 'font-black text-lg'} ${item.highlight ? 'text-indigo-600' : ''} ${item.italic ? 'italic text-slate-500' : ''}`}>
                                            {item.value ?? '—'}
                                        </Text>
                                    </div>
                                ))}
                            </div>
                        )}
                    </Card>

                    {/* Snapshots Section */}
                    <Card
                        title={
                            <div className="flex items-center space-x-3 py-1">
                                <div className="w-8 h-8 rounded-lg bg-indigo-50 flex items-center justify-center text-indigo-600">
                                    <FileTextOutlined />
                                </div>
                                <span className="font-black text-slate-800 tracking-tight text-lg uppercase">特征快照分析</span>
                            </div>
                        }
                        className="rounded-[2.5rem] border-none shadow-2xl shadow-slate-200/30"
                        styles={{ body: { padding: '32px' } }}
                    >
                        {!snapshots?.exists ? (
                            <Empty description="暂无快照数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                        ) : (
                            <div className="space-y-10">
                                <div className="grid grid-cols-2 md:grid-cols-4 gap-y-8">
                                    {[
                                        { label: '总行数', value: snapshots.total_rows?.toLocaleString(), color: 'text-indigo-600' },
                                        { label: '扫描成功', value: snapshots.scanned_files, color: 'text-emerald-500' },
                                        { label: '扫描失败', value: snapshots.failed_files, color: 'text-rose-500' },
                                        { label: '数据完整性', value: snapshots.error ? '异常' : '正常', color: snapshots.error ? 'text-rose-500' : 'text-emerald-500' }
                                    ].map((item, i) => (
                                        <div key={i} className="flex flex-col">
                                            <Text className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">{item.label}</Text>
                                            <Text className={`font-black text-xl tracking-tighter ${item.color}`}>{item.value ?? '—'}</Text>
                                        </div>
                                    ))}
                                </div>

                                {snapshots.suggested_periods && (
                                    <div className="p-6 rounded-3xl bg-slate-50 border border-slate-100">
                                        <div className="flex items-center space-x-2 mb-4">
                                            <CompassOutlined className="text-slate-400" />
                                            <span className="text-xs font-black text-slate-600 uppercase tracking-widest">推荐训练区间（全局）</span>
                                        </div>
                                        <div className="flex flex-wrap gap-4">
                                            {Object.entries(snapshots.suggested_periods).map(([key, period]: [string, any]) => (
                                                <div key={key} className="flex-1 min-w-[140px] p-4 bg-white rounded-2xl shadow-sm border border-slate-100">
                                                    <Text className="text-[10px] font-bold text-slate-400 uppercase block mb-1">{key} 集</Text>
                                                    <Text className="font-mono text-[11px] font-black text-slate-700">{period[0]} ~ {period[1]}</Text>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}

                                {snapshots?.metadata_files && snapshots.metadata_files.length > 0 && (
                                    <div className="space-y-4">
                                        <div className="flex items-center justify-between px-1">
                                            <Text className="text-[10px] font-black text-slate-400 uppercase tracking-widest">年度快照详情</Text>
                                            <Tag className="m-0 border-none bg-indigo-50 text-indigo-400 text-[9px] font-bold rounded-md">Total: {snapshots.metadata_files.length}</Tag>
                                        </div>
                                        <div className="space-y-3 max-h-[420px] overflow-y-auto pr-2 custom-scrollbar">
                                            {snapshots.metadata_files.map((m: any, idx: number) => (
                                                <div key={idx} className="group bg-white rounded-2xl p-4 border border-slate-100 flex items-center justify-between hover:border-indigo-200 hover:shadow-md transition-all duration-300">
                                                    <div className="flex items-center space-x-4">
                                                        <div className="w-10 h-10 rounded-xl bg-slate-50 flex items-center justify-center group-hover:bg-indigo-50 transition-colors">
                                                            <span className="text-slate-400 font-black text-xs group-hover:text-indigo-500">{m.year}</span>
                                                        </div>
                                                        <div className="space-y-1">
                                                            <div className="text-xs font-black text-slate-700 tracking-tight">
                                                                {m.start_date} <span className="text-slate-300 mx-1">/</span> {m.end_date}
                                                            </div>
                                                            <div className="flex items-center space-x-3 text-[10px] text-slate-400 font-medium">
                                                                <span className="flex items-center"><DatabaseOutlined className="mr-1 text-[9px]" /> {m.row_count.toLocaleString()} 样本</span>
                                                                <span className="flex items-center"><UserOutlined className="mr-1 text-[9px]" /> {m.symbol_count} 标的</span>
                                                            </div>
                                                        </div>
                                                    </div>
                                                    <div className="text-right">
                                                        <div className="text-[10px] font-black text-indigo-500 uppercase tracking-tight">{m.feature_dim} Features</div>
                                                        <div className="text-[8px] text-slate-300 font-mono mt-1 uppercase">{m.filename.split('.').slice(0, 2).join('.')}</div>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}
                    </Card>
                </Col>

                <Col span={24} lg={9} className="space-y-8">
                    {/* Maintenance Panel */}
                    <Card
                        className="rounded-[2.5rem] border-none shadow-xl shadow-slate-200/40 bg-white"
                        styles={{ body: { padding: '32px' } }}
                    >
                        <div className="flex items-center justify-between mb-8">
                            <div className="flex items-center space-x-3">
                                <div className="w-10 h-10 rounded-xl bg-indigo-50 flex items-center justify-center">
                                    <CloudSyncOutlined className="text-indigo-600 text-xl" />
                                </div>
                                <span className="text-slate-800 font-black text-xl uppercase tracking-tight">自动化维护</span>
                            </div>
                            <Tag className="m-0 bg-indigo-50 text-indigo-600 border-none rounded-full px-3 py-0.5 text-[10px] font-bold uppercase tracking-widest">一体化</Tag>
                        </div>

                        <div className="space-y-6">
                            <div className="p-5 rounded-2xl bg-slate-50 border border-slate-100">
                                <Title level={5} className="!text-slate-800 !font-black !mb-3 uppercase tracking-tight text-sm">日常同步任务包含：</Title>
                                <ul className="space-y-2 m-0 p-0 list-none">
                                    {[
                                        '增量拉取远程 PG 行情数据',
                                        '更新本地 Parquet 核心资产',
                                        '校准指标 (MA/换手率/收益率)',
                                        '增量更新 Qlib 二进制引擎数据',
                                        '计算 51 维模型特征（动量/波动率/流动性/资金流/风格因子）'
                                    ].map((text, i) => (
                                        <li key={i} className="flex items-start text-xs text-slate-500 font-medium">
                                            <CheckCircleFilled className="text-emerald-500 mt-0.5 mr-2" />
                                            {text}
                                        </li>
                                    ))}
                                </ul>
                            </div>
                            
                            <Space direction="vertical" className="w-full" size="middle">
                                <Button
                                    type="primary"
                                    block
                                    className="h-12 rounded-2xl bg-indigo-600 hover:bg-indigo-700 border-none font-black text-sm shadow-lg shadow-indigo-100 transition-all flex items-center justify-center"
                                    loading={dailySyncLoading}
                                    onClick={() => handleDailySync(true)}
                                    icon={<SyncOutlined />}
                                    disabled={!!syncTaskId}
                                >
                                    增量同步（多源聚合）
                                </Button>
                                <Button
                                    block
                                    className="h-12 rounded-2xl border-slate-200 text-slate-600 font-bold hover:bg-slate-50 transition-all"
                                    loading={dailySyncLoading}
                                    onClick={() => handleDailySync(false)}
                                    icon={<CloudDownloadOutlined />}
                                    disabled={!!syncTaskId}
                                >
                                    全量同步
                                </Button>
                                <Button
                                    block
                                    className="h-12 rounded-2xl border-slate-200 text-slate-600 font-bold hover:bg-slate-50 transition-all"
                                    loading={syncLoading}
                                    onClick={handleSyncOfficialData}
                                    icon={<ThunderboltOutlined />}
                                >
                                    旧版全量同步
                                </Button>
                                <Divider className="!my-2" />
                                <Button
                                    block
                                    className="h-12 rounded-2xl bg-emerald-600 hover:bg-emerald-700 border-none text-white font-black text-sm shadow-lg shadow-emerald-100 transition-all"
                                    loading={parquetLoading}
                                    onClick={() => handleUpdateFeatureParquet(false)}
                                    icon={<LineChartOutlined />}
                                >
                                    更新特征快照（补充缺失日期）
                                </Button>
                                <Button
                                    block
                                    className="h-12 rounded-2xl border-amber-200 text-amber-700 font-bold hover:bg-amber-50 transition-all"
                                    loading={parquetLoading}
                                    onClick={() => handleUpdateFeatureParquet(true)}
                                    icon={<SyncOutlined />}
                                >
                                    全量重建特征（覆盖全部日期）
                                </Button>
                                {syncTaskProgress && (
                                    <div className="p-4 rounded-2xl bg-blue-50 border border-blue-100 space-y-3">
                                        <div className="flex items-center gap-2">
                                            <Spin size="small" />
                                            <Text className="text-xs text-blue-600 font-bold">{syncStepProgress?.detail || syncTaskProgress}</Text>
                                        </div>
                                        {syncStepProgress && syncStepProgress.pct > 0 && (
                                            <div>
                                                <Progress
                                                    percent={syncStepProgress.pct}
                                                    size="small"
                                                    strokeColor={{ from: '#6366f1', to: '#10b981' }}
                                                    format={(pct) => <span className="text-[10px] font-bold text-slate-500">{pct}%</span>}
                                                />
                                                {syncStepProgress.total > 0 && (
                                                    <Text className="text-[10px] text-slate-400 mt-1 block">
                                                        {syncStepProgress.current}/{syncStepProgress.total} 只股票
                                                    </Text>
                                                )}
                                            </div>
                                        )}
                                        <div className="flex gap-1">
                                            {['init', 'pg_query', 'data_sync', 'qlib_bin', 'calibrate', 'parquet', 'done'].map((s, i) => {
                                                const stepOrder = ['init', 'pg_query', 'data_sync', 'qlib_bin', 'calibrate', 'parquet', 'done'];
                                                const currentIdx = stepOrder.indexOf(syncStepProgress?.step || '');
                                                const isActive = i === currentIdx;
                                                const isDone = i < currentIdx;
                                                return (
                                                    <div key={s} className={`h-1 flex-1 rounded-full transition-all duration-300 ${
                                                        isDone ? 'bg-emerald-400' :
                                                        isActive ? 'bg-indigo-500 animate-pulse' :
                                                        'bg-slate-200'
                                                    }`} />
                                                );
                                            })}
                                        </div>
                                        <div className="flex justify-between text-[8px] text-slate-400 font-medium">
                                            <span>初始化</span>
                                            <span>PG</span>
                                            <span>同步</span>
                                            <span>Qlib</span>
                                            <span>指标</span>
                                            <span>Parquet</span>
                                            <span>完成</span>
                                        </div>
                                    </div>
                                )}
                                {parquetResult && (
                                    <div className={`p-4 rounded-2xl border ${parquetResult.success ? 'bg-emerald-50 border-emerald-100' : 'bg-rose-50 border-rose-100'}`}>
                                        <Text className={`text-xs font-bold ${parquetResult.success ? 'text-emerald-600' : 'text-rose-600'}`}>
                                            {parquetResult.success ? '更新成功' : '更新失败'} (exit={parquetResult.exit_code})
                                        </Text>
                                        {parquetResult.stdout && (
                                            <pre className="mt-2 text-[10px] text-slate-500 bg-white p-2 rounded-lg max-h-32 overflow-auto whitespace-pre-wrap">
                                                {parquetResult.stdout.slice(-1000)}
                                            </pre>
                                        )}
                                        {parquetResult.stderr && !parquetResult.success && (
                                            <pre className="mt-2 text-[10px] text-rose-500 bg-white p-2 rounded-lg max-h-32 overflow-auto whitespace-pre-wrap">
                                                {parquetResult.stderr.slice(-1000)}
                                            </pre>
                                        )}
                                    </div>
                                )}
                            </Space>

                            <div className="bg-amber-50 border border-amber-100 p-4 rounded-2xl">
                                <div className="flex items-start">
                                    <InfoCircleOutlined className="text-amber-500 mt-0.5 mr-2" />
                                    <Text className="text-[11px] text-amber-700 font-medium leading-relaxed">
                                        增量同步：investment_data → baostock → akshare → eltdx 多源聚合，自动校准技术指标并更新 Qlib。
                                        Celery Beat 已配置每日 18:00 自动执行。
                                    </Text>
                                </div>
                            </div>
                        </div>
                    </Card>

                    {/* Sync Status Card */}
                    <Card
                        className="rounded-[2.5rem] border-none shadow-xl shadow-slate-200/40 bg-white"
                        styles={{ body: { padding: '32px' } }}
                    >
                        <div className="flex items-center justify-between mb-6">
                            <div className="flex items-center space-x-3">
                                <div className="w-10 h-10 rounded-xl bg-emerald-50 flex items-center justify-center">
                                    <SyncOutlined className="text-emerald-600 text-xl" />
                                </div>
                                <span className="text-slate-800 font-black text-xl uppercase tracking-tight">同步状态</span>
                            </div>
                            <Button
                                type="text"
                                size="small"
                                icon={<ReloadOutlined spin={syncStatusLoading} />}
                                onClick={loadSyncStatus}
                                className="text-slate-400"
                            />
                        </div>

                        {syncStatus ? (
                            <div className="space-y-4">
                                {syncStatus.last_sync && (
                                    <div className="grid grid-cols-2 gap-4">
                                        <div className="p-3 rounded-xl bg-slate-50">
                                            <Text className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block mb-1">最后同步</Text>
                                            <Text className="text-sm font-black text-slate-700">
                                                {syncStatus.last_sync.time ? dayjs(syncStatus.last_sync.time).format('MM-DD HH:mm') : '—'}
                                            </Text>
                                        </div>
                                        <div className="p-3 rounded-xl bg-slate-50">
                                            <Text className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block mb-1">模式</Text>
                                            <Tag color={syncStatus.last_sync.mode === 'incremental' ? 'green' : 'blue'} className="m-0 border-none font-bold rounded-lg">
                                                {syncStatus.last_sync.mode === 'incremental' ? '增量' : '全量'}
                                            </Tag>
                                        </div>
                                    </div>
                                )}

                                {syncStatus.last_sync?.sources && (
                                    <div className="p-4 rounded-2xl bg-slate-50 border border-slate-100">
                                        <Text className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block mb-3">数据源同步结果</Text>
                                        <div className="grid grid-cols-2 gap-3">
                                            {Object.entries(syncStatus.last_sync.sources).map(([name, count]: [string, any]) => (
                                                <div key={name} className="flex items-center justify-between p-2 bg-white rounded-lg">
                                                    <Text className="text-xs font-bold text-slate-600">{name}</Text>
                                                    <Tag color={count > 0 ? 'green' : 'default'} className="m-0 border-none text-[10px] font-bold rounded-md">
                                                        {count} 条
                                                    </Tag>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}

                                {syncStatus.stock_daily_latest && (
                                    <div className="p-4 rounded-2xl bg-slate-50 border border-slate-100">
                                        <Text className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block mb-3">stock_daily_latest 表</Text>
                                        <div className="grid grid-cols-3 gap-3">
                                            <div>
                                                <Text className="text-[10px] text-slate-400 block">最新日期</Text>
                                                <Text className="text-sm font-black text-slate-700">{syncStatus.stock_daily_latest.max_date || '—'}</Text>
                                            </div>
                                            <div>
                                                <Text className="text-[10px] text-slate-400 block">总行数</Text>
                                                <Text className="text-sm font-black text-indigo-600">{(syncStatus.stock_daily_latest.total_rows || 0).toLocaleString()}</Text>
                                            </div>
                                            <div>
                                                <Text className="text-[10px] text-slate-400 block">股票数</Text>
                                                <Text className="text-sm font-black text-emerald-600">{syncStatus.stock_daily_latest.symbol_count || '—'}</Text>
                                            </div>
                                        </div>
                                    </div>
                                )}

                                {syncStatus.qlib_data && (
                                    <div className="p-4 rounded-2xl bg-slate-50 border border-slate-100">
                                        <Text className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block mb-3">Qlib 数据</Text>
                                        <div className="grid grid-cols-2 gap-3">
                                            <div>
                                                <Text className="text-[10px] text-slate-400 block">日历最后日期</Text>
                                                <Text className="text-sm font-black text-slate-700">{syncStatus.qlib_data.calendar_last_date || '—'}</Text>
                                            </div>
                                            <div>
                                                <Text className="text-[10px] text-slate-400 block">标的数</Text>
                                                <Text className="text-sm font-black text-indigo-600">{syncStatus.qlib_data.instruments_count || '—'}</Text>
                                            </div>
                                        </div>
                                    </div>
                                )}
                            </div>
                        ) : (
                            <Empty
                                image={Empty.PRESENTED_IMAGE_SIMPLE}
                                description={
                                    <Text className="text-slate-400 text-xs">
                                        {syncStatusLoading ? '加载中...' : '暂无同步记录，点击上方按钮开始同步'}
                                    </Text>
                                }
                            />
                        )}
                    </Card>

                    {/* Issue Tracker cards */}
                    {snapshots?.exists && (olderSamples.length > 0 || invalidSamples.length > 0) && (
                        <div className="space-y-6">
                            <Card 
                                title={<span className="font-black text-rose-500 tracking-tight uppercase text-sm flex items-center"><WarningFilled className="mr-2" /> 数据滞后（Top {sampleSize}）</span>}
                                className="rounded-3xl border-none shadow-xl shadow-slate-200/20"
                                styles={{ body: { padding: '0 12px 12px' } }}
                            >
                                <Table<AdminFeatureSnapshotsOlderSample>
                                    size="small"
                                    pagination={false}
                                    rowKey={(r) => `${r.symbol}-${r.last_date}`}
                                    dataSource={olderSamples}
                                    columns={olderColumns}
                                    className="custom-table"
                                    locale={{ emptyText: '无滞后数据' }}
                                    scroll={{ y: 240 }}
                                />
                            </Card>
                            <Card 
                                title={<span className="font-black text-slate-400 tracking-tight uppercase text-sm flex items-center"><InfoCircleOutlined className="mr-2" /> 无效文件</span>}
                                className="rounded-3xl border-none shadow-xl shadow-slate-200/20"
                                styles={{ body: { padding: '0 12px 12px' } }}
                            >
                                <Table<AdminFeatureSnapshotsInvalidSample>
                                    size="small"
                                    pagination={false}
                                    rowKey={(r) => `${r.symbol}-${r.reason}-${r.file || ''}`}
                                    dataSource={invalidSamples}
                                    columns={invalidColumns}
                                    className="custom-table"
                                    locale={{ emptyText: '所有文件正常' }}
                                    scroll={{ y: 240 }}
                                />
                            </Card>
                        </div>
                    )}
                </Col>
            </Row>
        </div>
    );
};

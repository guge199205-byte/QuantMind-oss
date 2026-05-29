import React, { useEffect, useState } from 'react';
import { Card, Select, Table, Tag, Spin, Empty, Typography } from 'antd';
import { dataDashboardService, FieldInfo, FieldDataResponse } from '../services/dataDashboardService';

const { Text } = Typography;

const TIER_LABELS: Record<string, { color: string; text: string }> = {
    T1: { color: 'blue', text: '离线日级' },
    T2: { color: 'cyan', text: '分钟级' },
    T3: { color: 'green', text: '实时报价' },
    T4: { color: 'orange', text: '逐笔/订单流' },
    T5: { color: 'purple', text: '资金流' },
};

const FIELD_LABELS: Record<string, string> = {
    daily_kline: '日K线',
    minute_kline: '分钟K线',
    adj_factor: '复权因子',
    realtime_quote: '实时行情',
    tick: '逐笔成交',
    auction: '集合竞价',
    money_flow: '资金流向',
    financial_report: '财务报表',
    f10: 'F10基本信息',
    dragon_tiger: '龙虎榜',
    margin_trading: '融资融券',
    block_trade: '大宗交易',
    shareholder_count: '股东人数',
    dividend: '分红送转',
    share_unlock: '限售解禁',
    share_change: '股东变动',
    research_report: '研报',
    announcement: '公告',
    news: '新闻',
    sector: '行业板块',
    growth: '成长能力',
    operation: '营运能力',
    dupont: '杜邦分析',
    forecast: '业绩预告',
    performance_express: '业绩快报',
    futures_kline: '期货K线',
    options_chain: '期权链',
    hot_signal: '热点信号',
    institutional_holdings: '机构持仓',
    stock_screening: '选股指标',
    sec_filing: 'SEC文件',
    income_statement: '利润表',
    cash_flow: '现金流量表',
    major_holders: '主要股东',
    mutual_fund_holders: '基金持仓',
    recommendations: '分析师推荐',
    upgrades_downgrades: '评级变动',
    earnings_estimate: '盈利预测',
    earnings_dates: '财报日期',
    earnings_history: '财报历史',
    analyst_price_targets: '目标价',
    revenue_estimate: '营收预测',
    growth_estimates: '增长预测',
    sustainability: 'ESG可持续性',
    splits: '拆股',
    insider_transactions: '内部交易',
    calendar: '日历事件',
    valuation: '估值指标',
};

interface FieldBrowserProps {
    market: string;
    symbol: string;
}

export const FieldBrowser: React.FC<FieldBrowserProps> = ({ market, symbol }) => {
    const [fields, setFields] = useState<FieldInfo[]>([]);
    const [selectedField, setSelectedField] = useState<string>('');
    const [fieldData, setFieldData] = useState<FieldDataResponse | null>(null);
    const [loading, setLoading] = useState(false);
    const [fieldsLoading, setFieldsLoading] = useState(false);

    useEffect(() => {
        setFieldsLoading(true);
        dataDashboardService
            .getFields(market)
            .then((f) => {
                const list = Array.isArray(f) ? f : [];
                setFields(list);
                if (list.length > 0 && !selectedField) {
                    setSelectedField(list[0].field);
                }
            })
            .finally(() => setFieldsLoading(false));
    }, [market]);

    useEffect(() => {
        if (!selectedField || !symbol) return;
        setLoading(true);
        setFieldData(null);
        dataDashboardService
            .getFieldData(market, selectedField, symbol, 365)
            .then(setFieldData)
            .catch(() => setFieldData(null))
            .finally(() => setLoading(false));
    }, [market, selectedField, symbol]);

    // Build table columns from fieldData.columns
    const tableColumns = fieldData?.columns?.map((col) => ({
        title: col,
        dataIndex: col,
        key: col,
        ellipsis: true,
        width: 120,
        render: (v: any) => {
            if (v === null || v === undefined) return '—';
            if (typeof v === 'number') return v.toLocaleString(undefined, { maximumFractionDigits: 4 });
            if (typeof v === 'string' && v.length > 30) return v.substring(0, 30) + '...';
            return String(v);
        },
    })) || [];

    // Group fields by tier
    const grouped = fields.reduce<Record<string, FieldInfo[]>>((acc, f) => {
        const tier = f.tier || 'T1';
        if (!acc[tier]) acc[tier] = [];
        acc[tier].push(f);
        return acc;
    }, {});

    return (
        <div style={{ display: 'flex', gap: 16, minHeight: 400 }}>
            {/* Left: field list */}
            <Card
                size="small"
                title="数据字段"
                style={{ width: 240, flexShrink: 0 }}
                bodyStyle={{ padding: '8px', maxHeight: 500, overflowY: 'auto' }}
                loading={fieldsLoading}
            >
                {Object.entries(grouped)
                    .sort(([a], [b]) => a.localeCompare(b))
                    .map(([tier, items]) => (
                        <div key={tier} style={{ marginBottom: 8 }}>
                            <div style={{ fontSize: 11, color: '#6b7280', marginBottom: 4, paddingLeft: 4 }}>
                                <Tag color={TIER_LABELS[tier]?.color || 'default'} style={{ fontSize: 10 }}>
                                    {TIER_LABELS[tier]?.text || tier}
                                </Tag>
                            </div>
                            {items.map((f) => (
                                <div
                                    key={f.field}
                                    onClick={() => setSelectedField(f.field)}
                                    style={{
                                        padding: '4px 8px',
                                        cursor: 'pointer',
                                        borderRadius: 4,
                                        fontSize: 12,
                                        background: selectedField === f.field ? '#e0f2fe' : 'transparent',
                                        color: selectedField === f.field ? '#0369a1' : '#374151',
                                        fontWeight: selectedField === f.field ? 600 : 400,
                                        marginBottom: 1,
                                    }}
                                >
                                    {FIELD_LABELS[f.field] || f.field}
                                    <Text type="secondary" style={{ fontSize: 10, marginLeft: 4 }}>
                                        {f.primary}
                                    </Text>
                                </div>
                            ))}
                        </div>
                    ))}
            </Card>

            {/* Right: data table */}
            <Card
                size="small"
                title={
                    <span>
                        {FIELD_LABELS[selectedField] || selectedField}
                        {fieldData && (
                            <Tag style={{ marginLeft: 8 }} color="blue">
                                {fieldData.source_used} | {fieldData.count}条
                            </Tag>
                        )}
                    </span>
                }
                style={{ flex: 1 }}
                bodyStyle={{ padding: '8px', maxHeight: 500, overflowY: 'auto' }}
            >
                {loading ? (
                    <div style={{ textAlign: 'center', padding: 40 }}>
                        <Spin tip="加载中..." />
                    </div>
                ) : fieldData && fieldData.data.length > 0 ? (
                    <Table
                        dataSource={fieldData.data}
                        columns={tableColumns}
                        size="small"
                        scroll={{ x: 'max-content', y: 380 }}
                        pagination={{ pageSize: 50, showSizeChanger: true, showTotal: (t) => `共 ${t} 条` }}
                        rowKey={(_, i) => String(i)}
                    />
                ) : (
                    <Empty
                        description={fieldData ? '该字段暂无数据' : '选择字段查看数据'}
                        style={{ padding: 40 }}
                    />
                )}
            </Card>
        </div>
    );
};

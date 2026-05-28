import React, { useCallback, useEffect, useState } from 'react';
import { Card, Tabs, Tag, Typography, Space, Spin, message, List, Button, Empty } from 'antd';
import {
    StockOutlined,
    BarChartOutlined,
    AppstoreOutlined,
    BankOutlined,
    StarFilled,
    ReloadOutlined,
} from '@ant-design/icons';
import { KlineChart } from '../components/KlineChart';
import { TradingViewChart } from '../components/TradingViewChart';
import { StockSearch } from '../components/StockSearch';
import { FieldBrowser } from '../components/FieldBrowser';
import { SectorExplorer } from '../components/SectorExplorer';
import { MarketOverview } from '../components/MarketOverview';
import { dataDashboardService, KlineItem } from '../services/dataDashboardService';
import { researchService } from '../../../services/researchService';

const { Title, Text } = Typography;

type Market = 'A' | 'HK' | 'US';

const MARKET_TABS = [
    { key: 'A', label: 'A股', icon: <StockOutlined /> },
    { key: 'HK', label: '港股', icon: <BankOutlined /> },
    { key: 'US', label: '美股', icon: <BarChartOutlined /> },
];

const DEFAULT_SYMBOLS: Record<string, { symbol: string; name: string }> = {
    A: { symbol: '600519.SH', name: '贵州茅台' },
    HK: { symbol: '00700.HK', name: '腾讯控股' },
    US: { symbol: 'AAPL', name: 'Apple' },
};

interface WatchlistItem {
    symbol: string;
    stockName: string | null;
    tags: string[];
}

const DashboardPage: React.FC = () => {
    const [market, setMarket] = useState<Market>('A');
    const [symbol, setSymbol] = useState(DEFAULT_SYMBOLS.A.symbol);
    const [symbolName, setSymbolName] = useState(DEFAULT_SYMBOLS.A.name);
    const [klineData, setKlineData] = useState<KlineItem[]>([]);
    const [klineLoading, setKlineLoading] = useState(false);
    const [klineSource, setKlineSource] = useState('');
    const [fieldCount, setFieldCount] = useState(0);
    const [activeTab, setActiveTab] = useState('fields');

    // Watchlist state
    const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
    const [watchlistLoading, setWatchlistLoading] = useState(false);

    // Load watchlist from research platform
    const loadWatchlist = useCallback(async () => {
        setWatchlistLoading(true);
        try {
            const result = await researchService.getWatchlist(100, 0);
            setWatchlist(result.items.map((item: any) => ({
                symbol: item.symbol,
                stockName: item.stockName,
                tags: item.tags || [],
            })));
        } catch {
            setWatchlist([]);
        } finally {
            setWatchlistLoading(false);
        }
    }, []);

    useEffect(() => {
        loadWatchlist();
    }, [loadWatchlist]);

    // Load field count for current market
    useEffect(() => {
        dataDashboardService.getFields(market).then((f) => setFieldCount(f.length)).catch(() => {});
    }, [market]);

    // Load K-line data
    const loadKline = useCallback(async (m: Market, sym: string) => {
        setKlineLoading(true);
        try {
            const resp = await dataDashboardService.getKline(m, sym, 120);
            setKlineData(resp.items || []);
            setKlineSource(resp.source_used || '');
        } catch (e: any) {
            message.error(`K线数据加载失败: ${e?.message || e}`);
            setKlineData([]);
            setKlineSource('');
        } finally {
            setKlineLoading(false);
        }
    }, []);

    // When market changes, reset to default symbol
    useEffect(() => {
        const def = DEFAULT_SYMBOLS[market];
        if (def) {
            setSymbol(def.symbol);
            setSymbolName(def.name);
            loadKline(market, def.symbol);
        }
    }, [market, loadKline]);

    // Handle stock selection from search
    const handleStockSelect = useCallback(
        (sym: string, name: string) => {
            setSymbol(sym);
            setSymbolName(name);
            loadKline(market, sym);
        },
        [market, loadKline],
    );

    // Handle watchlist item click
    const handleWatchlistClick = useCallback(
        (item: WatchlistItem) => {
            // Auto-detect market from symbol
            const code = item.symbol.replace(/\.\w+$/, '');
            let m: Market = 'A';
            if (item.symbol.includes('.HK') || item.symbol.startsWith('0') && code.length === 5) {
                m = 'HK';
            } else if (!/^\d{6}$/.test(code)) {
                m = 'US';
            }
            setMarket(m);
            setSymbol(item.symbol);
            setSymbolName(item.stockName || item.symbol);
            loadKline(m, item.symbol);
        },
        [loadKline],
    );

    return (
        <div style={{ padding: '16px 24px', background: '#f8fafc', minHeight: '100vh' }}>
            {/* Header */}
            <div style={{ marginBottom: 16 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                    <Space>
                        <Title level={4} style={{ margin: 0 }}>数据看板</Title>
                        <Tag color="blue">{fieldCount} 个字段</Tag>
                    </Space>
                    <StockSearch market={market} onSelect={handleStockSelect} />
                </div>

                {/* Market Tabs */}
                <Tabs
                    activeKey={market}
                    onChange={(k) => setMarket(k as Market)}
                    items={MARKET_TABS.map((t) => ({
                        key: t.key,
                        label: (
                            <span>
                                {t.icon}
                                <span style={{ marginLeft: 6 }}>{t.label}</span>
                            </span>
                        ),
                    }))}
                    style={{ marginBottom: 0 }}
                />
            </div>

            {/* Market Overview */}
            <div style={{ marginBottom: 16 }}>
                <MarketOverview market={market} />
            </div>

            {/* Main content: Watchlist sidebar + K-line chart */}
            <div style={{ display: 'flex', gap: 16, marginBottom: 16 }}>
                {/* Watchlist sidebar */}
                <Card
                    size="small"
                    title={
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <Space>
                                <StarFilled style={{ color: '#f59e0b' }} />
                                <Text strong>自选股</Text>
                                <Tag>{watchlist.length}</Tag>
                            </Space>
                            <Button
                                type="text"
                                size="small"
                                icon={<ReloadOutlined />}
                                onClick={loadWatchlist}
                                loading={watchlistLoading}
                            />
                        </div>
                    }
                    style={{ width: 220, flexShrink: 0 }}
                    bodyStyle={{ padding: '4px 8px', maxHeight: 580, overflowY: 'auto' }}
                >
                    {watchlistLoading && watchlist.length === 0 ? (
                        <div style={{ textAlign: 'center', padding: 20 }}>
                            <Spin size="small" />
                        </div>
                    ) : watchlist.length === 0 ? (
                        <Empty
                            image={Empty.PRESENTED_IMAGE_SIMPLE}
                            description="暂无自选股"
                            style={{ padding: '20px 0' }}
                        >
                            <Text type="secondary" style={{ fontSize: 11 }}>
                                去投研平台添加自选
                            </Text>
                        </Empty>
                    ) : (
                        <List
                            dataSource={watchlist}
                            size="small"
                            renderItem={(item) => (
                                <div
                                    onClick={() => handleWatchlistClick(item)}
                                    style={{
                                        padding: '8px 10px',
                                        cursor: 'pointer',
                                        borderRadius: 6,
                                        marginBottom: 2,
                                        background: symbol === item.symbol ? '#e0f2fe' : 'transparent',
                                        border: symbol === item.symbol ? '1px solid #7dd3fc' : '1px solid transparent',
                                        transition: 'all 0.2s',
                                    }}
                                    onMouseEnter={(e) => {
                                        if (symbol !== item.symbol) {
                                            e.currentTarget.style.background = '#f8fafc';
                                        }
                                    }}
                                    onMouseLeave={(e) => {
                                        if (symbol !== item.symbol) {
                                            e.currentTarget.style.background = 'transparent';
                                        }
                                    }}
                                >
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                        <Text strong style={{ fontSize: 13 }}>{item.symbol.replace(/\.\w+$/, '')}</Text>
                                        {item.tags.length > 0 && (
                                            <Tag color="blue" style={{ fontSize: 10, margin: 0 }}>
                                                {item.tags[0]}
                                            </Tag>
                                        )}
                                    </div>
                                    <Text type="secondary" style={{ fontSize: 11 }}>
                                        {item.stockName || '—'}
                                    </Text>
                                </div>
                            )}
                        />
                    )}
                </Card>

                {/* K-line Chart */}
                <Card
                    size="small"
                    style={{ flex: 1 }}
                    bodyStyle={{ padding: '8px' }}
                    title={
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <Space>
                                <Text strong>{symbol}</Text>
                                <Text type="secondary">{symbolName}</Text>
                                {klineSource && (
                                    <Tag color="green" style={{ fontSize: 10 }}>
                                        {klineSource}
                                    </Tag>
                                )}
                            </Space>
                        </div>
                    }
                >
                    {klineLoading ? (
                        <div style={{ height: 550, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                            <Spin tip="加载K线数据..." />
                        </div>
                    ) : (
                        <TradingViewChart data={klineData} height={550} />
                    )}
                </Card>
            </div>

            {/* Bottom tabs: Fields / Sectors */}
            <Card size="small" bodyStyle={{ padding: '8px 16px' }}>
                <Tabs
                    activeKey={activeTab}
                    onChange={setActiveTab}
                    items={[
                        {
                            key: 'fields',
                            label: (
                                <span>
                                    <AppstoreOutlined />
                                    <span style={{ marginLeft: 6 }}>数据字段浏览</span>
                                </span>
                            ),
                            children: <FieldBrowser market={market} symbol={symbol} />,
                        },
                        {
                            key: 'sectors',
                            label: (
                                <span>
                                    <BankOutlined />
                                    <span style={{ marginLeft: 6 }}>行业板块</span>
                                </span>
                            ),
                            children: <SectorExplorer market={market} symbol={symbol} />,
                        },
                    ]}
                />
            </Card>
        </div>
    );
};

export default DashboardPage;

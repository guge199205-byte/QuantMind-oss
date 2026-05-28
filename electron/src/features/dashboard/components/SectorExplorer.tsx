import React, { useEffect, useState } from 'react';
import { Card, Table, Tag, Spin, Empty, Typography } from 'antd';
import { dataDashboardService } from '../services/dataDashboardService';

const { Text } = Typography;

interface SectorExplorerProps {
    market: string;
    symbol: string;
}

export const SectorExplorer: React.FC<SectorExplorerProps> = ({ market, symbol }) => {
    const [data, setData] = useState<Record<string, any>[]>([]);
    const [loading, setLoading] = useState(false);
    const [columns, setColumns] = useState<any[]>([]);

    useEffect(() => {
        if (!symbol) return;
        setLoading(true);
        dataDashboardService
            .getSectors(market, symbol)
            .then((rows) => {
                setData(rows);
                if (rows.length > 0) {
                    const cols = Object.keys(rows[0]).map((k) => ({
                        title: k,
                        dataIndex: k,
                        key: k,
                        ellipsis: true,
                        width: 150,
                        render: (v: any) => {
                            if (v === null || v === undefined) return '—';
                            if (typeof v === 'number') return v.toLocaleString(undefined, { maximumFractionDigits: 4 });
                            return String(v);
                        },
                    }));
                    setColumns(cols);
                }
            })
            .catch(() => {
                setData([]);
                setColumns([]);
            })
            .finally(() => setLoading(false));
    }, [market, symbol]);

    return (
        <Card
            size="small"
            title="行业板块信息"
            extra={
                data.length > 0 ? (
                    <Tag color="blue">{data.length}条记录</Tag>
                ) : null
            }
        >
            {loading ? (
                <div style={{ textAlign: 'center', padding: 40 }}>
                    <Spin tip="加载行业数据..." />
                </div>
            ) : data.length > 0 ? (
                <Table
                    dataSource={data}
                    columns={columns}
                    size="small"
                    scroll={{ x: 'max-content' }}
                    pagination={false}
                    rowKey={(_, i) => String(i)}
                />
            ) : (
                <Empty description="暂无行业板块数据" style={{ padding: 40 }} />
            )}
        </Card>
    );
};

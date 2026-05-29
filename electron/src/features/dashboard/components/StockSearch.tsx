import React, { useCallback, useRef, useState } from 'react';
import { AutoComplete, Input } from 'antd';
import { SearchOutlined } from '@ant-design/icons';
import { dataDashboardService, SearchResult } from '../services/dataDashboardService';

interface StockSearchProps {
    market: string;
    onSelect: (symbol: string, name: string) => void;
    style?: React.CSSProperties;
}

export const StockSearch: React.FC<StockSearchProps> = ({ market, onSelect, style }) => {
    const [options, setOptions] = useState<{ value: string; label: React.ReactNode; item: SearchResult }[]>([]);
    const [loading, setLoading] = useState(false);
    const timerRef = useRef<any>(null);

    const doSearch = useCallback(
        async (keyword: string) => {
            if (!keyword || keyword.length < 1) {
                setOptions([]);
                return;
            }
            setLoading(true);
            try {
                const results = await dataDashboardService.search(keyword, market, 15);
                setOptions(
                    results.map((r) => ({
                        value: r.symbol,
                        label: (
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <span style={{ fontWeight: 500 }}>{r.symbol}</span>
                                <span style={{ color: '#6b7280', fontSize: 12 }}>{r.name}</span>
                            </div>
                        ),
                        item: r,
                    })),
                );
            } catch {
                setOptions([]);
            } finally {
                setLoading(false);
            }
        },
        [market],
    );

    const handleSearch = (value: string) => {
        if (timerRef.current) clearTimeout(timerRef.current);
        timerRef.current = setTimeout(() => doSearch(value), 300);
    };

    const handleSelect = (value: string) => {
        const opt = options.find((o) => o.value === value);
        if (opt) {
            onSelect(opt.item.symbol, opt.item.name);
        }
    };

    return (
        <AutoComplete
            options={options}
            onSearch={handleSearch}
            onSelect={handleSelect}
            style={{ width: 320, ...style }}
        >
            <Input
                placeholder={`搜索${market === 'A' ? 'A股' : market === 'HK' ? '港股' : '美股'}代码/名称...`}
                prefix={<SearchOutlined style={{ color: '#9ca3af' }} />}
                allowClear
                loading={loading}
            />
        </AutoComplete>
    );
};

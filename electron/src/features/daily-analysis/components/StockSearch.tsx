import React, { useState, useCallback } from 'react';
import { AutoComplete, Input } from 'antd';
import { SearchOutlined } from '@ant-design/icons';
import { dailyAnalysisService } from '../services/dailyAnalysisService';
import type { StockSearchResult } from '../types';

interface StockSearchProps {
  value?: string;
  onChange?: (value: string, stock?: StockSearchResult) => void;
  placeholder?: string;
}

export const StockSearch: React.FC<StockSearchProps> = ({
  value,
  onChange,
  placeholder = '输入股票代码或名称搜索',
}) => {
  const [options, setOptions] = useState<{ value: string; label: React.ReactNode; stock: StockSearchResult }[]>([]);
  const [loading, setLoading] = useState(false);

  const handleSearch = useCallback(async (text: string) => {
    if (!text || text.length < 1) {
      setOptions([]);
      return;
    }
    setLoading(true);
    try {
      const results = await dailyAnalysisService.searchStocks(text, 10);
      setOptions(
        results.map((r) => ({
          value: r.code,
          label: (
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>{r.name}</span>
              <span style={{ color: '#999', fontSize: 12 }}>{r.code}</span>
            </div>
          ),
          stock: r,
        })),
      );
    } catch {
      setOptions([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleSelect = useCallback(
    (val: string) => {
      const opt = options.find((o) => o.value === val);
      onChange?.(val, opt?.stock);
    },
    [options, onChange],
  );

  return (
    <AutoComplete
      value={value}
      options={options}
      onSearch={handleSearch}
      onSelect={handleSelect}
      onChange={(val) => onChange?.(val)}
      style={{ width: '100%' }}
    >
      <Input
        size="large"
        placeholder={placeholder}
        prefix={<SearchOutlined style={{ color: '#bfbfbf' }} />}
        allowClear
      />
    </AutoComplete>
  );
};

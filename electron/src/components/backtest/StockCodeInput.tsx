/**
 * 股票代码输入组件
 * 优先使用本地JSON数据（极快），降级到腾讯API（有价格和名称）
 */
import React, { useState, useRef, useEffect } from 'react';
import { Search, X, Info } from 'lucide-react';
import { stockListService, Stock } from '../../services/stockListService';
import { SERVICE_ENDPOINTS } from '../../config/services';

interface StockOption extends Stock {
  price?: number;
}

interface Props {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  allowEmpty?: boolean;
}

export const StockCodeInput: React.FC<Props> = ({
  value,
  onChange,
  placeholder = '输入代码或简称搜索（如：000001 或 平安银行）',
  allowEmpty = false
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [options, setOptions] = useState<StockOption[]>([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const [loading, setLoading] = useState(false);
  const [dataSource, setDataSource] = useState<'local' | 'api'>('local');
  const inputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // 启动时加载本地数据
  useEffect(() => {
    stockListService.load().catch(err => {
      console.error('Failed to load stock list:', err);
    });
  }, []);

  // 搜索本地数据
  const searchLocalStocks = (query: string): StockOption[] => {
    try {
      return stockListService.search(query, 10);
    } catch (error) {
      console.error('Local search failed:', error);
      return [];
    }
  };

  // 搜索腾讯API（降级方案，包含实时价格和名称）
  const searchTencentStocks = async (query: string): Promise<StockOption[]> => {
    try {
      const keyword = String(query || '').trim();
      if (!keyword) return [];

      const response = await fetch(
        `${SERVICE_ENDPOINTS.API_GATEWAY}/stocks/search?q=${encodeURIComponent(keyword)}&limit=10`
      );
      const payload = await response.json();
      const rawList = Array.isArray(payload?.results)
        ? payload.results
        : (Array.isArray(payload?.data) ? payload.data : []);

      return rawList
        .map((item: any): StockOption | null => {
          const symbol = String(item?.code || item?.symbol || '').trim();
          const name = String(item?.name || '').trim();
          if (!symbol || !name) return null;
          const [code = symbol, market = ''] = symbol.split('.');
          return {
            symbol,
            code,
            market,
            name,
            price: undefined,
          };
        })
        .filter((s): s is StockOption => s !== null)
        .slice(0, 10);
    } catch (error) {
      console.error('Gateway stock search failed:', error);
      return [];
    }
  };

  // 搜索股票
  const searchStocks = async (query: string) => {
    if (!query || query.length < 2) {
      setOptions([]);
      return;
    }

    setLoading(true);
    try {
      let results: StockOption[] = [];

      // 优先使用本地数据
      if (stockListService.isLoaded()) {
        results = searchLocalStocks(query);
        setDataSource('local');

        // 如果本地搜索没结果，尝试使用腾讯API（可能是简称搜索）
        if (results.length === 0) {
          console.log('[StockCodeInput] 本地无结果，尝试腾讯API');
          results = await searchTencentStocks(query);
          setDataSource('api');
        }
      } else {
        // 本地数据未加载，使用腾讯API
        results = await searchTencentStocks(query);
        setDataSource('api');
      }

      setOptions(results);
    } catch (error) {
      console.error('Stock search failed:', error);
      setOptions([]);
    } finally {
      setLoading(false);
    }
  };

  // 防抖搜索
  useEffect(() => {
    const timer = setTimeout(() => {
      if (searchQuery) {
        searchStocks(searchQuery);
      } else {
        setOptions([]);
      }
    }, 300);

    return () => clearTimeout(timer);
  }, [searchQuery]);

  // 点击外部关闭下拉框
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target as Node) &&
        inputRef.current &&
        !inputRef.current.contains(event.target as Node)
      ) {
        setShowDropdown(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSelect = (option: StockOption) => {
    onChange(option.symbol);
    setSearchQuery('');
    setShowDropdown(false);
    setOptions([]);
  };

  const handleClear = () => {
    onChange('');
    setSearchQuery('');
    setOptions([]);
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newValue = e.target.value;
    setSearchQuery(newValue);
    setShowDropdown(true);

    // 如果是直接输入标准格式的代码（如 000001.SZ），立即更新
    if (/^\d{6}\.(SZ|SH|BJ)$/.test(newValue)) {
      onChange(newValue);
    }
  };

  return (
    <div className="relative">
      <div className="relative">
        <input
          ref={inputRef}
          type="text"
          value={searchQuery || value}
          onChange={handleInputChange}
          onFocus={() => setShowDropdown(true)}
          placeholder={placeholder}
          className="w-full px-3 py-2 pr-20 bg-white border border-gray-200 rounded-2xl text-gray-800 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
        />

        <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1">
          {loading && (
            <div className="animate-spin h-4 w-4 border-2 border-blue-500 border-t-transparent rounded-full" />
          )}
          {value && (
            <button
              onClick={handleClear}
              className="p-1 hover:bg-gray-100 rounded-2xl"
              title="清空"
            >
              <X className="h-4 w-4 text-gray-400" />
            </button>
          )}
          <Search className="h-4 w-4 text-gray-400" />
        </div>
      </div>

      {/* 下拉选项 */}
      {showDropdown && options.length > 0 && (
        <div
          ref={dropdownRef}
          className="absolute z-50 w-full mt-1 bg-white border border-gray-200 rounded-2xl shadow-lg max-h-64 overflow-y-auto"
        >
          {options.map((option, index) => (
            <div
              key={index}
              onClick={() => handleSelect(option)}
              className="px-3 py-2 hover:bg-blue-50 cursor-pointer border-b border-gray-100 last:border-b-0"
            >
              <div className="flex justify-between items-center">
                <div className="flex-1">
                  {option.name && (
                    <span className="font-medium text-gray-800">{option.name}</span>
                  )}
                  <span className={option.name ? "ml-2 text-sm text-gray-500" : "font-medium text-gray-800"}>
                    {option.symbol}
                  </span>
                  {option.market && (
                    <span className="ml-2 text-xs px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded-2xl">
                      {option.market}
                    </span>
                  )}
                </div>
                {option.price && (
                  <span className="text-sm text-red-600 font-mono">
                    ¥{option.price.toFixed(2)}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* 提示信息 */}
      <div className="flex items-center justify-between mt-1">
        {allowEmpty && !value && (
          <div className="flex items-center gap-1 text-xs text-blue-600">
            <Info className="h-3 w-3" />
            <span>动态选股策略可以留空</span>
          </div>
        )}
        {options.length > 0 && (
          <div className="flex items-center gap-1 text-xs text-gray-500 ml-auto">
            <span>
              {dataSource === 'local'
                ? `数据源：本地 (${stockListService.getTotal()}只)`
                : '数据源：腾讯财经（含实时价格）'}
            </span>
          </div>
        )}
      </div>
    </div>
  );
};

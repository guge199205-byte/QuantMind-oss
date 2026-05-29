/**
 * 市场数据查看器组件
 */

import React, { useState } from 'react';
import { Search, RefreshCw, TrendingUp, Calendar, AlertCircle } from 'lucide-react';
import ReactECharts from 'echarts-for-react';
import { qlibDataService, QlibMarketData } from '../../services/qlib/qlibDataService';
import { BACKTEST_CONFIG } from '../../config/backtest';

export const MarketDataViewer: React.FC = () => {
  const [symbol, setSymbol] = useState('000001.SZ');
  const [startDate, setStartDate] = useState('2026-01-02');
  const [endDate, setEndDate] = useState('2026-12-31');
  const [data, setData] = useState<QlibMarketData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [viewMode, setViewMode] = useState<'chart' | 'table'>('chart');

  const handleSearch = async () => {
    if (!symbol.trim()) {
      setError('请输入股票代码');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const result = await qlibDataService.getMarketData(symbol, startDate, endDate, false);
      setData(result);
    } catch (err: any) {
      setError(err.message || '获取数据失败');
    } finally {
      setLoading(false);
    }
  };

  const getKlineOption = () => {
    if (!data?.data.length) return {};
    const dates = data.data.map(d => d.date);
    const values = data.data.map(d => [d.open, d.close, d.low, d.high]);
    const volumes = data.data.map(d => d.volume);
    return {
      title: { text: `${data.symbol} K线图`, left: 'center' },
      tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
      grid: [
        { left: '10%', right: '10%', top: '15%', height: '50%' },
        { left: '10%', right: '10%', top: '70%', height: '15%' }
      ],
      xAxis: [
        { type: 'category', data: dates, gridIndex: 0 },
        { type: 'category', data: dates, gridIndex: 1, axisLabel: { show: false } }
      ],
      yAxis: [
        { scale: true, gridIndex: 0 },
        { scale: true, gridIndex: 1, axisLabel: { show: false } }
      ],
      dataZoom: [
        { type: 'inside', xAxisIndex: [0, 1], start: 80, end: 100 },
        { show: true, xAxisIndex: [0, 1], bottom: '5%', start: 80, end: 100 }
      ],
      series: [
        {
          name: 'K线',
          type: 'candlestick',
          data: values,
          itemStyle: { color: '#ef4444', color0: '#10b981', borderColor: '#ef4444', borderColor0: '#10b981' }
        },
        { name: '成交量', type: 'bar', xAxisIndex: 1, yAxisIndex: 1, data: volumes, itemStyle: { color: '#3b82f6' } }
      ]
    };
  };

  return (
    <div className="h-full flex flex-col bg-white rounded-lg border shadow-sm">
      <div className="border-b p-4">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-bold">市场数据查询</h2>
          <div className="flex gap-2">
            <button onClick={() => setViewMode('chart')} className={`px-3 py-1.5 rounded-lg text-sm ${viewMode === 'chart' ? 'bg-blue-500 text-white' : 'bg-gray-100'}`}>K线图</button>
            <button onClick={() => setViewMode('table')} className={`px-3 py-1.5 rounded-lg text-sm ${viewMode === 'table' ? 'bg-blue-500 text-white' : 'bg-gray-100'}`}>表格</button>
          </div>
        </div>
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-4">
          <div className="flex items-center gap-2 text-blue-800 text-sm">
            <Calendar className="w-4 h-4" />
            <span>Qlib真实数据范围: 2026-01-02 至 2026-12-31 | 完整: 2005-01-04 至 2025-12-31</span>
          </div>
        </div>
        <div className="grid grid-cols-4 gap-3">
          <div>
            <label className="block text-sm mb-1.5">股票代码</label>
            <input type="text" value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())} placeholder="000001.SZ" className="w-full px-3 py-2 border rounded-lg" />
          </div>
          <div>
            <label className="block text-sm mb-1.5">开始日期</label>
            <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} min={BACKTEST_CONFIG.QLIB.DATA_START} max={BACKTEST_CONFIG.QLIB.DATA_END} className="w-full px-3 py-2 border rounded-lg" />
          </div>
          <div>
            <label className="block text-sm mb-1.5">结束日期</label>
            <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} min={BACKTEST_CONFIG.QLIB.DATA_START} max={BACKTEST_CONFIG.QLIB.DATA_END} className="w-full px-3 py-2 border rounded-lg" />
          </div>
          <div className="flex items-end">
            <button onClick={handleSearch} disabled={loading} className="w-full px-4 py-2 bg-blue-500 text-white rounded-lg disabled:opacity-50 flex items-center justify-center gap-2">
              {loading ? <><RefreshCw className="w-4 h-4 animate-spin" />查询中</> : <><Search className="w-4 h-4" />查询</>}
            </button>
          </div>
        </div>
        {error && <div className="mt-3 bg-red-50 border border-red-200 rounded-lg p-3"><div className="flex items-start gap-2"><AlertCircle className="w-4 h-4 text-red-600 mt-0.5" /><div className="text-sm text-red-700">{error}</div></div></div>}
      </div>
      <div className="flex-1 overflow-auto p-4">
        {loading ? <div className="flex items-center justify-center h-full"><RefreshCw className="w-12 h-12 text-blue-500 animate-spin" /></div> :
         data ? (viewMode === 'chart' ? <ReactECharts option={getKlineOption()} style={{ height: '100%', width: '100%' }} /> : <div>表格视图</div>) :
         <div className="flex items-center justify-center h-full text-gray-400"><TrendingUp className="w-16 h-16 opacity-50" /></div>}
      </div>
      {data && <div className="border-t px-4 py-3 bg-gray-50 text-sm text-gray-600">数据来源: Qlib | 共 {data.data.length} 条 | {data.start_date} ~ {data.end_date}</div>}
    </div>
  );
};

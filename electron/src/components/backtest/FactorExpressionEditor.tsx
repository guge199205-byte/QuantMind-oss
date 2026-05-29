import React, { useState } from 'react';
import { Plus, Trash2, Play, Activity } from 'lucide-react';
import ReactECharts from 'echarts-for-react';
import { qlibDataService, FactorExpression, FactorCalculationResult } from '../../services/qlib/qlibDataService';

export const FactorExpressionEditor: React.FC = () => {
  const [symbol, setSymbol] = useState('000001.SZ');
  const [startDate, setStartDate] = useState('2026-01-01');
  const [endDate, setEndDate] = useState('2026-12-31');
  const [expressions, setExpressions] = useState<FactorExpression[]>([
    { expression: '$close', name: 'Close' },
    { expression: 'Ref($close, 1) / $close - 1', name: 'Return' },
    { expression: 'Mean($close, 5)', name: 'MA5' }
  ]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<FactorCalculationResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleAddExpression = () => {
    setExpressions([...expressions, { expression: '', name: '' }]);
  };

  const handleRemoveExpression = (index: number) => {
    const newExpressions = [...expressions];
    newExpressions.splice(index, 1);
    setExpressions(newExpressions);
  };

  const handleExpressionChange = (index: number, field: keyof FactorExpression, value: string) => {
    const newExpressions = [...expressions];
    newExpressions[index] = { ...newExpressions[index], [field]: value };
    setExpressions(newExpressions);
  };

  const handleCalculate = async () => {
    setLoading(true);
    setError(null);
    try {
      // Filter out empty expressions
      const validExpressions = expressions.filter(e => e.expression.trim() !== '');
      if (validExpressions.length === 0) {
        throw new Error("请至少输入一个因子表达式");
      }

      const res = await qlibDataService.calculateFactors(
        symbol,
        startDate,
        endDate,
        validExpressions
      );
      setResult(res);
    } catch (err: unknown) {
      console.error(err);
      setError(err instanceof Error ? err.message : String(err) || "计算失败");
    } finally {
      setLoading(false);
    }
  };

  // Prepare chart option
  const getChartOption = () => {
    if (!result || !result.factors || result.factors.length === 0) return {};

    const dates = result.factors[0].data.map(d => d.date);
    const series = result.factors.map(factor => ({
      name: factor.name || factor.expression,
      type: 'line',
      data: factor.data.map(d => d.value),
      showSymbol: false,
      smooth: true
    }));

    return {
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross' }
      },
      legend: {
        data: result.factors.map(f => f.name || f.expression)
      },
      grid: {
        left: '3%',
        right: '4%',
        bottom: '3%',
        containLabel: true
      },
      xAxis: {
        type: 'category',
        boundaryGap: false,
        data: dates
      },
      yAxis: {
        type: 'value',
        scale: true // Auto scale
      },
      dataZoom: [
        { type: 'inside', start: 0, end: 100 },
        { type: 'slider', start: 0, end: 100 }
      ],
      series: series
    };
  };

  return (
    <div className="flex flex-col h-full bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
      <div className="p-4 border-b border-gray-200 flex justify-between items-center bg-gray-50">
        <h2 className="text-lg font-semibold text-gray-800 flex items-center gap-2">
          <Activity className="w-5 h-5 text-blue-600" />
          因子表达式计算器
        </h2>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Left Panel: Configuration */}
        <div className="w-[400px] border-r border-gray-200 p-4 overflow-y-auto flex flex-col gap-6 bg-gray-50/50">

          {/* Base Settings */}
          <div className="space-y-4">
            <h3 className="text-sm font-medium text-gray-700 uppercase tracking-wider">基础设置</h3>
            <div className="grid grid-cols-1 gap-3">
              <div>
                <label className="block text-xs text-gray-500 mb-1">股票代码</label>
                <input
                  value={symbol}
                  onChange={(e) => setSymbol(e.target.value)}
                  className="w-full px-3 py-2 bg-white border border-gray-300 rounded-2xl text-sm focus:outline-none focus:border-blue-500 transition-colors"
                  placeholder="000001.SZ"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-gray-500 mb-1">开始日期</label>
                  <input
                    type="date"
                    value={startDate}
                    onChange={(e) => setStartDate(e.target.value)}
                    className="w-full px-3 py-2 bg-white border border-gray-300 rounded-2xl text-sm focus:outline-none focus:border-blue-500 transition-colors"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">结束日期</label>
                  <input
                    type="date"
                    value={endDate}
                    onChange={(e) => setEndDate(e.target.value)}
                    className="w-full px-3 py-2 bg-white border border-gray-300 rounded-2xl text-sm focus:outline-none focus:border-blue-500 transition-colors"
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Expressions */}
          <div className="flex-1 flex flex-col min-h-0">
            <div className="flex justify-between items-center mb-2">
              <h3 className="text-sm font-medium text-gray-700 uppercase tracking-wider">因子表达式</h3>
              <button
                type="button"
                onClick={handleAddExpression}
                aria-label="添加表达式"
                title="添加表达式"
                className="text-blue-600 hover:text-blue-700 p-1 rounded-2xl hover:bg-blue-50 transition-colors"
              >
                <Plus className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3 flex-1 overflow-y-auto pr-1">
              {expressions.map((expr, index) => (
                <div key={index} className="flex gap-2 items-start group">
                  <div className="flex-1 space-y-1">
                    <input
                      value={expr.name || ''}
                      onChange={(e) => handleExpressionChange(index, 'name', e.target.value)}
                      placeholder="因子名称 (可选)"
                      className="w-full px-2 py-1 bg-transparent border-b border-gray-200 text-xs text-gray-600 focus:outline-none focus:border-blue-400 placeholder-gray-300"
                    />
                    <input
                      value={expr.expression}
                      onChange={(e) => handleExpressionChange(index, 'expression', e.target.value)}
                      placeholder="输入 Qlib 表达式, e.g. Ref($close, 1)"
                      className="w-full px-3 py-2 bg-white border border-gray-300 rounded-2xl text-sm font-mono text-gray-800 focus:outline-none focus:border-blue-500 focus:shadow-sm transition-all"
                    />
                  </div>
                  <button
                    type="button"
                    onClick={() => handleRemoveExpression(index)}
                    aria-label={`删除表达式 ${index + 1}`}
                    title="删除表达式"
                    className="text-gray-400 hover:text-red-500 p-1.5 mt-4 opacity-0 group-hover:opacity-100 transition-all"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          </div>

          {/* Calculate Button */}
          <button
            onClick={handleCalculate}
            disabled={loading}
            className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-2xl shadow-sm hover:shadow transition-all disabled:opacity-50 disabled:cursor-not-allowed flex justify-center items-center gap-2 text-sm font-medium"
          >
            {loading ? (
              <span className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent"></span>
            ) : (
              <Play className="w-4 h-4" />
            )}
            计算因子
          </button>

          {error && (
            <div className="p-3 bg-red-50 text-red-600 text-sm rounded-2xl border border-red-100 break-all">
              {error}
            </div>
          )}
        </div>

        {/* Right Panel: Visualization */}
        <div className="flex-1 bg-white p-4 flex flex-col min-w-0">
          {result ? (
            <div className="flex-1 flex flex-col min-h-0">
               <div className="mb-4 flex justify-between items-center">
                  <h3 className="font-medium text-gray-800">计算结果: {result.symbol}</h3>
                  <span className="text-xs text-gray-500">
                    {result.factors.length} 个因子, {result.factors[0]?.data.length || 0} 条记录
                  </span>
               </div>
               <div className="flex-1 w-full min-h-0">
                 <ReactECharts
                    option={getChartOption()}
                    style={{ height: '100%', width: '100%' }}
                    notMerge={true}
                 />
               </div>
            </div>
          ) : (
            <div className="flex-1 flex items-center justify-center text-gray-400 flex-col gap-3">
              <Activity className="w-16 h-16 opacity-20" />
              <p>在左侧配置因子并点击计算</p>
              <div className="text-xs text-gray-300 max-w-xs text-center">
                支持 Qlib 表达式语法，例如: <br/>
                Ref($close, 1) / $close - 1 <br/>
                Mean($volume, 20)
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

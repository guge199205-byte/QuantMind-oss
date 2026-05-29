/**
 * 因子表达式编辑器组件
 * 支持Qlib因子表达式编写、验证和计算
 */

import React, { useState } from 'react';
import { Plus, Trash2, Play, Save, BookOpen, AlertCircle, TrendingUp, RefreshCw } from 'lucide-react';
import ReactECharts from 'echarts-for-react';
import { qlibDataService, FactorExpression, FactorCalculationResult } from '../../services/qlib/qlibDataService';
import { BACKTEST_CONFIG } from '../../config/backtest';

// 常用因子模板
const FACTOR_TEMPLATES = [
  { name: '日收益率', expr: '($close-Ref($close, 1))/Ref($close, 1)', description: '当日收盘价相对前一日的收益率' },
  { name: '5日ROC', expr: 'ROC($close, 5)', description: '5日价格变化率' },
  { name: '20日MA', expr: 'Mean($close, 20)', description: '20日移动平均线' },
  { name: '成交量比率', expr: '$volume/Mean($volume, 5)', description: '当日成交量相对5日均量的比率' },
  { name: 'RSI(6)', expr: 'RSI($close, 6)', description: '6日相对强弱指标' },
  { name: '振幅', expr: '($high-$low)/$close', description: '日内振幅' },
  { name: '上影线', expr: '($high-Max($open, $close))/$close', description: '上影线比率' },
  { name: '下影线', expr: '(Min($open, $close)-$low)/$close', description: '下影线比率' },
];

interface Factor {
  id: string;
  name: string;
  expression: string;
}

export const FactorExpressionEditor: React.FC = () => {
  const [symbol, setSymbol] = useState('000001.SZ');
  const [startDate, setStartDate] = useState('2026-01-02');
  const [endDate, setEndDate] = useState('2026-12-31');
  const [factors, setFactors] = useState<Factor[]>([
    { id: '1', name: '日收益率', expression: '($close-Ref($close, 1))/Ref($close, 1)' },
  ]);
  const [result, setResult] = useState<FactorCalculationResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showTemplates, setShowTemplates] = useState(false);

  const addFactor = () => {
    setFactors([...factors, { id: Date.now().toString(), name: '', expression: '' }]);
  };

  const removeFactor = (id: string) => {
    setFactors(factors.filter(f => f.id !== id));
  };

  const updateFactor = (id: string, field: 'name' | 'expression', value: string) => {
    setFactors(factors.map(f => f.id === id ? { ...f, [field]: value } : f));
  };

  const applyTemplate = (template: typeof FACTOR_TEMPLATES[0]) => {
    addFactor();
    const newId = Date.now().toString();
    setFactors([...factors, { id: newId, name: template.name, expression: template.expr }]);
    setShowTemplates(false);
  };

  const handleCalculate = async () => {
    if (!symbol.trim()) {
      setError('请输入股票代码');
      return;
    }

    const validFactors = factors.filter(f => f.expression.trim());
    if (validFactors.length === 0) {
      setError('请至少添加一个有效的因子表达式');
      return;
    }

    setLoading(true);
    setError('');
    setResult(null);

    try {
      const expressions: FactorExpression[] = validFactors.map(f => ({
        name: f.name || f.expression,
        expression: f.expression,
      }));

      const data = await qlibDataService.calculateFactors(symbol, startDate, endDate, expressions);
      setResult(data);
    } catch (err: any) {
      setError(err.message || '因子计算失败');
      console.error('[FactorEditor] Error:', err);
    } finally {
      setLoading(false);
    }
  };

  const getChartOption = () => {
    if (!result || !result.factors.length) return {};

    const dates = result.factors[0].data.map(d => d.date);
    const series = result.factors.map((factor, idx) => ({
      name: factor.name,
      type: 'line',
      data: factor.data.map(d => d.value),
      smooth: true,
    }));

    return {
      title: { text: `${result.symbol} 因子时间序列`, left: 'center' },
      tooltip: { trigger: 'axis' },
      legend: { top: 30, data: result.factors.map(f => f.name) },
      grid: { left: '10%', right: '10%', top: '20%', bottom: '15%' },
      xAxis: { type: 'category', data: dates, boundaryGap: false },
      yAxis: { type: 'value', scale: true },
      dataZoom: [
        { type: 'inside', start: 80, end: 100 },
        { show: true, start: 80, end: 100 }
      ],
      series,
    };
  };

  return (
    <div className="h-full flex flex-col bg-white rounded-lg border shadow-sm">
      <div className="border-b p-4">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-bold text-gray-800">因子表达式编辑器</h2>
          <button onClick={() => setShowTemplates(!showTemplates)} className="px-3 py-1.5 bg-purple-100 text-purple-700 rounded-lg hover:bg-purple-200 transition-colors flex items-center gap-2">
            <BookOpen className="w-4 h-4" />
            因子模板
          </button>
        </div>

        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-4">
          <div className="text-sm text-blue-800">
            <div className="font-medium mb-1">Qlib因子表达式语法</div>
            <div className="text-xs space-y-1">
              <div>• 基础字段: $open, $high, $low, $close, $volume</div>
              <div>• 函数: Mean(), Ref(), ROC(), RSI(), Max(), Min(), Std(), Corr()</div>
              <div>• 运算符: +, -, *, /, &gt;, &lt;, ==, &amp;&amp;, ||</div>
            </div>
          </div>
        </div>

        {showTemplates && (
          <div className="mb-4 bg-gray-50 border rounded-lg p-4 max-h-60 overflow-y-auto">
            <div className="grid grid-cols-2 gap-2">
              {FACTOR_TEMPLATES.map((template, idx) => (
                <button key={idx} onClick={() => applyTemplate(template)} className="text-left p-3 bg-white hover:bg-blue-50 rounded-lg border transition-colors">
                  <div className="font-medium text-sm text-gray-800">{template.name}</div>
                  <div className="text-xs text-gray-600 mt-1 font-mono">{template.expr}</div>
                  <div className="text-xs text-gray-500 mt-1">{template.description}</div>
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="grid grid-cols-3 gap-3 mb-4">
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
        </div>

        {error && (
          <div className="mb-4 bg-red-50 border border-red-200 rounded-lg p-3">
            <div className="flex items-start gap-2">
              <AlertCircle className="w-4 h-4 text-red-600 mt-0.5" />
              <div className="text-sm text-red-700">{error}</div>
            </div>
          </div>
        )}
      </div>

      <div className="flex-1 overflow-auto">
        <div className="grid grid-cols-2 gap-4 p-4 h-full">
          <div className="space-y-3 overflow-y-auto">
            <div className="flex items-center justify-between mb-2">
              <h3 className="font-medium text-gray-800">因子列表</h3>
              <button onClick={addFactor} className="px-3 py-1.5 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors flex items-center gap-1 text-sm">
                <Plus className="w-4 h-4" />
                添加
              </button>
            </div>

            {factors.map((factor) => (
              <div key={factor.id} className="bg-gray-50 border rounded-lg p-3">
                <div className="flex items-center justify-between mb-2">
                  <input type="text" value={factor.name} onChange={(e) => updateFactor(factor.id, 'name', e.target.value)} placeholder="因子名称" className="flex-1 px-2 py-1 text-sm border rounded" />
                  <button onClick={() => removeFactor(factor.id)} className="ml-2 p-1 text-red-600 hover:bg-red-50 rounded">
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
                <textarea value={factor.expression} onChange={(e) => updateFactor(factor.id, 'expression', e.target.value)} placeholder="因子表达式 (例: $close/Ref($close, 1) - 1)" rows={3} className="w-full px-2 py-1 text-sm font-mono border rounded resize-none" />
              </div>
            ))}

            <button onClick={handleCalculate} disabled={loading} className="w-full py-2.5 bg-green-500 text-white rounded-lg hover:bg-green-600 disabled:opacity-50 transition-colors flex items-center justify-center gap-2">
              {loading ? <><RefreshCw className="w-4 h-4 animate-spin" />计算中</> : <><Play className="w-4 h-4" />计算因子</>}
            </button>
          </div>

          <div className="border rounded-lg overflow-hidden">
            {loading ? (
              <div className="flex items-center justify-center h-full">
                <RefreshCw className="w-12 h-12 text-blue-500 animate-spin" />
              </div>
            ) : result ? (
              <div className="h-full flex flex-col">
                <div className="flex-1">
                  <ReactECharts option={getChartOption()} style={{ height: '100%', width: '100%' }} />
                </div>
                <div className="border-t p-3 bg-gray-50">
                  <div className="text-sm text-gray-600">
                    因子数量: {result.factors.length} | 数据点: {result.factors[0]?.data.length || 0}
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex items-center justify-center h-full text-gray-400">
                <div className="text-center">
                  <TrendingUp className="w-16 h-16 mx-auto mb-4 opacity-50" />
                  <p>配置因子后点击"计算因子"</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

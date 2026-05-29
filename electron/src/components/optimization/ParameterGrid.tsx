import React, { useState } from 'react';
import { Play, Settings, AlertCircle } from 'lucide-react';
import { DatePicker } from 'antd';
import dayjs from 'dayjs';
import { BACKTEST_CONFIG } from '../../config/backtest';

const { RangePicker } = DatePicker;

export interface ParameterRange {
  name: string;
  min: number;
  max: number;
  step: number;
  values?: number[];
}

export interface GridSearchConfig {
  strategy: 'TopkDropoutStrategy';
  parameters: {
    topk: ParameterRange;
    n_drop: ParameterRange;
  };
  metric: 'annual_return' | 'sharpe_ratio' | 'max_drawdown' | 'information_ratio';
  initialCapital: number;
  dateRange: {
    startDate: string;
    endDate: string;
  };
}

interface Props {
  onStartOptimization: (config: GridSearchConfig) => void;
  isRunning: boolean;
  workerReady?: boolean;
  workerMessage?: string;
}

export const ParameterGrid: React.FC<Props> = ({ onStartOptimization, isRunning, workerReady = true, workerMessage = '' }) => {
  const [topkMin, setTopkMin] = useState(20);
  const [topkMax, setTopkMax] = useState(60);
  const [topkStep, setTopkStep] = useState(10);

  const [nDropMin, setNDropMin] = useState(1);
  const [nDropMax, setNDropMax] = useState(5);
  const [nDropStep, setNDropStep] = useState(1);

  const [initialCapital, setInitialCapital] = useState(1000000);
  const [metric, setMetric] = useState<GridSearchConfig['metric']>('sharpe_ratio');
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs, dayjs.Dayjs]>([
    dayjs(BACKTEST_CONFIG.QLIB.DEFAULT_START),
    dayjs(BACKTEST_CONFIG.QLIB.DEFAULT_END)
  ]);

  const [error, setError] = useState<string>('');

  const disabledDate = (current: dayjs.Dayjs) => {
    // 限制在 2023-01-01 到 2025-12-30
    const start = dayjs(BACKTEST_CONFIG.QLIB.DATA_START);
    const end = dayjs(BACKTEST_CONFIG.QLIB.DATA_END);
    return current && (current < start.startOf('day') || current > end.endOf('day'));
  };

  const generateValues = (min: number, max: number, step: number): number[] => {
    const values: number[] = [];
    for (let i = min; i <= max; i += step) {
      values.push(i);
    }
    return values;
  };

  const calculateCombinations = (): number => {
    const topkValues = generateValues(topkMin, topkMax, topkStep);
    const nDropValues = generateValues(nDropMin, nDropMax, nDropStep);
    return topkValues.length * nDropValues.length;
  };

  const validateInputs = (): string | null => {
    if (topkMin >= topkMax) return 'topk最小值必须小于最大值';
    if (nDropMin >= nDropMax) return 'n_drop最小值必须小于最大值';
    if (topkStep <= 0) return 'topk步长必须大于0';
    if (nDropStep <= 0) return 'n_drop步长必须大于0';
    if (topkMin < 10) return 'topk最小值不能小于10';
    if (topkMax > 80) return 'topk最大值不能超过80（Beta 限制）';
    if (nDropMin < 1) return 'n_drop最小值不能小于1';
    if (nDropMax > 20) return 'n_drop最大值不能超过20（Beta 限制）';
    if (nDropMax >= topkMin) return 'n_drop最大值必须小于topk最小值';

    const combinations = calculateCombinations();
    if (combinations > 40) return `组合数过多 (${combinations})，Beta 模式最多允许40组`;

    if (!dateRange || !dateRange[0] || !dateRange[1]) return '请选择有效的时间范围';
    
    // 显式校验边界
    const selectedStart = dateRange[0].format('YYYY-MM-DD');
    const selectedEnd = dateRange[1].format('YYYY-MM-DD');
    if (selectedStart < BACKTEST_CONFIG.QLIB.DATA_START || selectedEnd > BACKTEST_CONFIG.QLIB.DATA_END) {
      return `日期范围超出数据覆盖范围 (${BACKTEST_CONFIG.QLIB.DATA_START} 至 ${BACKTEST_CONFIG.QLIB.DATA_END})`;
    }

    if (!workerReady) return workerMessage || '引擎队列不可用，暂时无法启动参数优化';

    return null;
  };

  const handleStart = () => {
    const validationError = validateInputs();
    if (validationError) {
      setError(validationError);
      return;
    }

    setError('');

    const config: GridSearchConfig = {
      strategy: 'TopkDropoutStrategy',
      parameters: {
        topk: {
          name: 'topk',
          min: topkMin,
          max: topkMax,
          step: topkStep,
          values: generateValues(topkMin, topkMax, topkStep)
        },
        n_drop: {
          name: 'n_drop',
          min: nDropMin,
          max: nDropMax,
          step: nDropStep,
          values: generateValues(nDropMin, nDropMax, nDropStep)
        }
      },
      metric,
      initialCapital,
      dateRange: {
        startDate: dateRange[0].format('YYYY-MM-DD'),
        endDate: dateRange[1].format('YYYY-MM-DD')
      }
    };

    onStartOptimization(config);
  };

  const combinations = calculateCombinations();

  return (
    <div className="bg-white rounded-2xl shadow p-6 mb-6">
      <div className="flex items-center gap-2 mb-4">
        <Settings className="w-5 h-5 text-blue-600" />
        <h3 className="text-lg font-semibold">网格搜索配置</h3>
      </div>

      <div className="grid grid-cols-2 gap-6 mb-6">
        {/* topk 参数 */}
        <div className="space-y-4">
          <div className="flex items-center gap-2 mb-2">
            <span className="font-medium text-gray-700">topk 参数范围</span>
            <span className="text-xs text-gray-500">(选股数量)</span>
          </div>

          <div className="grid grid-cols-3 gap-2">
            <div>
              <label className="block text-xs text-gray-600 mb-1">最小值</label>
              <input
                type="number"
                value={topkMin}
                onChange={(e) => setTopkMin(Number(e.target.value))}
                disabled={isRunning}
                className="w-full px-3 py-2 border border-gray-300 rounded-2xl focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-600 mb-1">最大值</label>
              <input
                type="number"
                value={topkMax}
                onChange={(e) => setTopkMax(Number(e.target.value))}
                disabled={isRunning}
                className="w-full px-3 py-2 border border-gray-300 rounded-2xl focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-600 mb-1">步长</label>
              <input
                type="number"
                value={topkStep}
                onChange={(e) => setTopkStep(Number(e.target.value))}
                disabled={isRunning}
                className="w-full px-3 py-2 border border-gray-300 rounded-2xl focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>
        </div>

        {/* n_drop 参数 */}
        <div className="space-y-4">
          <div className="flex items-center gap-2 mb-2">
            <span className="font-medium text-gray-700">n_drop 参数范围</span>
            <span className="text-xs text-gray-500">(每期调仓数量)</span>
          </div>

          <div className="grid grid-cols-3 gap-2">
            <div>
              <label className="block text-xs text-gray-600 mb-1">最小值</label>
              <input
                type="number"
                value={nDropMin}
                onChange={(e) => setNDropMin(Number(e.target.value))}
                disabled={isRunning}
                className="w-full px-3 py-2 border border-gray-300 rounded-2xl focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-600 mb-1">最大值</label>
              <input
                type="number"
                value={nDropMax}
                onChange={(e) => setNDropMax(Number(e.target.value))}
                disabled={isRunning}
                className="w-full px-3 py-2 border border-gray-300 rounded-2xl focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-600 mb-1">步长</label>
              <input
                type="number"
                value={nDropStep}
                onChange={(e) => setNDropStep(Number(e.target.value))}
                disabled={isRunning}
                className="w-full px-3 py-2 border border-gray-300 rounded-2xl focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>
        </div>
      </div>

      {/* 优化目标与初始资金 */}
      <div className="grid grid-cols-2 gap-6 mb-6">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            优化目标指标
          </label>
          <select
            value={metric}
            onChange={(e) => setMetric(e.target.value as GridSearchConfig['metric'])}
            disabled={isRunning}
            className="w-full px-3 py-2 border border-gray-300 rounded-2xl focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="sharpe_ratio">夏普比率 (Sharpe Ratio)</option>
            <option value="annual_return">年化收益率 (Annual Return)</option>
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            初始资金 (元)
          </label>
          <input
            type="number"
            value={initialCapital}
            onChange={(e) => setInitialCapital(Number(e.target.value))}
            disabled={isRunning}
            className="w-full px-3 py-2 border border-gray-300 rounded-2xl focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="请输入初始资金"
          />
        </div>
      </div>

      {/* 错误提示 */}
      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-2xl flex items-start gap-2">
          <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
          <span className="text-sm text-red-800">{error}</span>
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 mb-4">
        {/* 统计信息 */}
        <div className="bg-blue-50 border border-blue-200 rounded-2xl p-4">
          <div className="grid grid-cols-3 gap-4 text-center">
            <div>
              <div className="text-2xl font-bold text-blue-900">{combinations}</div>
              <div className="text-xs text-blue-700">本次预计评估组数</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-blue-900">
                {generateValues(topkMin, topkMax, topkStep).length}
              </div>
              <div className="text-xs text-blue-700">topk取值数</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-blue-900">
                {generateValues(nDropMin, nDropMax, nDropStep).length}
              </div>
              <div className="text-xs text-blue-700">n_drop取值数</div>
            </div>
          </div>
          <div className="mt-3 text-center text-xs text-blue-700">
            系统上限 40 组，超过将被前后端同时拒绝
          </div>
        </div>

        {/* Qlib 数据范围选择 */}
        <div className="p-3 bg-amber-50 border border-amber-200 rounded-2xl flex flex-col gap-2">
          <span className="text-sm font-medium text-amber-900">回测数据范围</span>
          <RangePicker
            value={dateRange}
            onChange={(dates) => dates && setDateRange([dates[0] as dayjs.Dayjs, dates[1] as dayjs.Dayjs])}
            disabled={isRunning}
            disabledDate={disabledDate}
            className="w-full rounded-2xl"
            style={{ padding: '8px 12px' }}
          />
          <p className="text-xs text-amber-700 mt-1">
            * 系统完整数据覆盖范围: {BACKTEST_CONFIG.QLIB.DATA_START} 至 {BACKTEST_CONFIG.QLIB.DATA_END}
          </p>
        </div>
      </div>

      {/* 开始按钮 */}
      <button
        onClick={handleStart}
        disabled={isRunning || !!validateInputs()}
        className="w-full px-4 py-3 bg-gradient-to-r from-blue-600 to-indigo-600 text-white rounded-2xl font-medium hover:from-blue-700 hover:to-indigo-700 disabled:from-gray-400 disabled:to-gray-400 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2"
      >
        <Play className="w-5 h-5" />
        {isRunning ? '优化进行中...' : '开始网格搜索'}
      </button>
      {!workerReady && (
        <div className="mt-3 text-sm text-red-600">
          {workerMessage || '当前队列不可用，请先启动 Celery worker 后重试'}
        </div>
      )}
    </div>
  );
};

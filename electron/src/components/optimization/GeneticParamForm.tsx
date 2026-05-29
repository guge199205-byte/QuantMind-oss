import React, { useState, useEffect } from 'react';
import { Settings, AlertCircle, RefreshCw } from 'lucide-react';
import { DatePicker } from 'antd';
import dayjs from 'dayjs';
import { BACKTEST_CONFIG } from '../../config/backtest';

const { RangePicker } = DatePicker;

// 参数范围定义
export interface ParameterRange {
    name: string;
    min: number;
    max: number;
    step: number;
}

// 遗传算法配置接口
export interface GeneticConfig {
    strategy: 'WeightedStrategy';
    // 策略参数范围
    parameters: {
        topk: ParameterRange;
        min_score: ParameterRange;
        max_weight: ParameterRange;
    };
    // 遗传算法超参数
    ga: {
        population_size: number;
        generations: number;
        mutation_rate: number;
    };
    metric: 'sharpe_ratio' | 'annual_return' | 'max_drawdown' | 'information_ratio';
    dateRange: {
        startDate: string;
        endDate: string;
    };
}

interface Props {
    onStartOptimization: (config: GeneticConfig) => void;
    isRunning: boolean;
}

export const GeneticParamForm: React.FC<Props> = ({ onStartOptimization, isRunning }) => {
    // === 策略参数范围 ===
    const [topkMin, setTopkMin] = useState(10);
    const [topkMax, setTopkMax] = useState(50);
    const [topkStep, setTopkStep] = useState(10);

    const [minScoreMin, setMinScoreMin] = useState(0.01);
    const [minScoreMax, setMinScoreMax] = useState(0.05);
    const [minScoreStep, setMinScoreStep] = useState(0.01);

    const [maxWeightMin, setMaxWeightMin] = useState(0.1);
    const [maxWeightMax, setMaxWeightMax] = useState(1.0);
    const [maxWeightStep, setMaxWeightStep] = useState(0.1);

    // === GA 超参数 ===
    const [populationSize, setPopulationSize] = useState(20);
    const [generations, setGenerations] = useState(10);
    const [mutationRate, setMutationRate] = useState(0.1);

    const [metric, setMetric] = useState<GeneticConfig['metric']>('sharpe_ratio');
    const [dateRange, setDateRange] = useState<[dayjs.Dayjs, dayjs.Dayjs]>([
        dayjs(BACKTEST_CONFIG.QLIB.DATA_START),
        dayjs(BACKTEST_CONFIG.QLIB.DATA_END)
    ]);

    const [error, setError] = useState<string>('');

    const validateInputs = (): string | null => {
        // 基础范围检查
        if (topkMin >= topkMax) return 'topk最小值必须小于最大值';
        if (minScoreMin > minScoreMax) return 'min_score最小值必须小于等于最大值'; // min_score可以相等
        if (maxWeightMin > maxWeightMax) return 'max_weight最小值必须小于等于最大值';

        if (topkMin < 5) return 'topk最小值不能小于5';
        if (populationSize < 4) return '种群大小不能小于4 (至少需要保留精英和繁衍)';
        if (generations < 1) return '代数不能小于1';

        if (!dateRange || !dateRange[0] || !dateRange[1]) return '请选择有效的时间范围';

        return null;
    };

    const handleStart = () => {
        const validationError = validateInputs();
        if (validationError) {
            setError(validationError);
            return;
        }

        setError('');

        const config: GeneticConfig = {
            strategy: 'WeightedStrategy',
            parameters: {
                topk: {
                    name: 'topk',
                    min: topkMin,
                    max: topkMax,
                    step: topkStep
                },
                min_score: {
                    name: 'min_score',
                    min: minScoreMin,
                    max: minScoreMax,
                    step: minScoreStep
                },
                max_weight: {
                    name: 'max_weight',
                    min: maxWeightMin,
                    max: maxWeightMax,
                    step: maxWeightStep
                }
            },
            ga: {
                population_size: populationSize,
                generations: generations,
                mutation_rate: mutationRate
            },
            metric,
            dateRange: {
                startDate: dateRange[0].format('YYYY-MM-DD'),
                endDate: dateRange[1].format('YYYY-MM-DD')
            }
        };

        onStartOptimization(config);
    };

    // 估算总评估次数
    const totalEvaluations = populationSize * generations;

    return (
        <div className="bg-white rounded-2xl shadow p-6 mb-6">
            <div className="flex items-center gap-2 mb-4">
                <Settings className="w-5 h-5 text-indigo-600" />
                <h3 className="text-lg font-semibold">遗传算法配置 (WeightedStrategy)</h3>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-6">
                {/* 左列：策略参数范围 */}
                <div className="space-y-6">
                    <div className="flex items-center gap-2 border-b border-gray-100 pb-2">
                        <span className="font-medium text-gray-800">策略参数搜索空间</span>
                    </div>

                    {/* topk */}
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">TopK (持仓数量)</label>
                        <div className="grid grid-cols-3 gap-2">
                            <input type="number" placeholder="Min" value={topkMin} onChange={e => setTopkMin(Number(e.target.value))} disabled={isRunning} className="w-full px-3 py-2 border rounded-xl text-sm" />
                            <input type="number" placeholder="Max" value={topkMax} onChange={e => setTopkMax(Number(e.target.value))} disabled={isRunning} className="w-full px-3 py-2 border rounded-xl text-sm" />
                            <input type="number" placeholder="Step" value={topkStep} onChange={e => setTopkStep(Number(e.target.value))} disabled={isRunning} className="w-full px-3 py-2 border rounded-xl text-sm" />
                        </div>
                    </div>

                    {/* min_score */}
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Min Score (入选阈值)</label>
                        <div className="grid grid-cols-3 gap-2">
                            <input type="number" step="0.01" placeholder="Min" value={minScoreMin} onChange={e => setMinScoreMin(Number(e.target.value))} disabled={isRunning} className="w-full px-3 py-2 border rounded-xl text-sm" />
                            <input type="number" step="0.01" placeholder="Max" value={minScoreMax} onChange={e => setMinScoreMax(Number(e.target.value))} disabled={isRunning} className="w-full px-3 py-2 border rounded-xl text-sm" />
                            <input type="number" step="0.01" placeholder="Step" value={minScoreStep} onChange={e => setMinScoreStep(Number(e.target.value))} disabled={isRunning} className="w-full px-3 py-2 border rounded-xl text-sm" />
                        </div>
                    </div>

                    {/* max_weight */}
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Max Weight (单标权重上限)</label>
                        <div className="grid grid-cols-3 gap-2">
                            <input type="number" step="0.1" placeholder="Min" value={maxWeightMin} onChange={e => setMaxWeightMin(Number(e.target.value))} disabled={isRunning} className="w-full px-3 py-2 border rounded-xl text-sm" />
                            <input type="number" step="0.1" placeholder="Max" value={maxWeightMax} onChange={e => setMaxWeightMax(Number(e.target.value))} disabled={isRunning} className="w-full px-3 py-2 border rounded-xl text-sm" />
                            <input type="number" step="0.1" placeholder="Step" value={maxWeightStep} onChange={e => setMaxWeightStep(Number(e.target.value))} disabled={isRunning} className="w-full px-3 py-2 border rounded-xl text-sm" />
                        </div>
                    </div>
                </div>

                {/* 右列：GA参数 & 通用设置 */}
                <div className="space-y-6">
                    <div className="flex items-center gap-2 border-b border-gray-100 pb-2">
                        <span className="font-medium text-gray-800">遗传算法超参数</span>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <label className="block text-sm text-gray-600 mb-1">种群大小 (Population)</label>
                            <input
                                type="number"
                                value={populationSize}
                                onChange={(e) => setPopulationSize(Number(e.target.value))}
                                disabled={isRunning}
                                className="w-full px-3 py-2 border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500"
                            />
                        </div>
                        <div>
                            <label className="block text-sm text-gray-600 mb-1">迭代代数 (Generations)</label>
                            <input
                                type="number"
                                value={generations}
                                onChange={(e) => setGenerations(Number(e.target.value))}
                                disabled={isRunning}
                                className="w-full px-3 py-2 border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500"
                            />
                        </div>
                    </div>

                    <div>
                        <label className="block text-sm text-gray-600 mb-1">变异率 (Mutation Rate)</label>
                        <div className="flex items-center gap-2">
                            <input
                                type="range"
                                min="0.01"
                                max="0.5"
                                step="0.01"
                                value={mutationRate}
                                onChange={(e) => setMutationRate(Number(e.target.value))}
                                disabled={isRunning}
                                className="flex-1"
                            />
                            <span className="text-sm text-gray-700 w-12 text-right">{mutationRate}</span>
                        </div>
                    </div>

                    {/* 优化目标 */}
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                            优化目标指标
                        </label>
                        <select
                            value={metric}
                            onChange={(e) => setMetric(e.target.value as GeneticConfig['metric'])}
                            disabled={isRunning}
                            className="w-full px-3 py-2 border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500"
                        >
                            <option value="sharpe_ratio">夏普比率 (Sharpe Ratio)</option>
                            <option value="annual_return">年化收益率 (Annual Return)</option>
                            <option value="information_ratio">信息比率 (Information Ratio)</option>
                            <option value="max_drawdown">最大回撤 (Max Drawdown - 越小越好)</option>
                        </select>
                    </div>

                    {/* Qlib 数据范围选择 */}
                    <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl flex flex-col gap-2">
                        <span className="text-sm font-medium text-amber-900">回测数据范围</span>
                        <RangePicker
                            value={dateRange}
                            onChange={(dates) => dates && setDateRange([dates[0] as dayjs.Dayjs, dates[1] as dayjs.Dayjs])}
                            disabled={isRunning}
                            className="w-full rounded-xl"
                            style={{ padding: '8px 12px' }}
                        />
                    </div>
                </div>
            </div>

            {/* 统计信息 */}
            <div className="bg-indigo-50 border border-indigo-100 rounded-xl p-3 mb-6 flex items-center justify-between text-indigo-900 text-sm">
                <div className="flex items-center gap-2">
                    <RefreshCw className="w-4 h-4" />
                    <span>预计最大评估次数: <strong>{totalEvaluations}</strong> 次回测</span>
                </div>
                <div className="text-xs opacity-75">
                    (种群 {populationSize} × 代数 {generations})
                </div>
            </div>

            {/* 错误提示 */}
            {error && (
                <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-xl flex items-start gap-2">
                    <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
                    <span className="text-sm text-red-800">{error}</span>
                </div>
            )}

            {/* 开始按钮 */}
            <button
                onClick={handleStart}
                disabled={isRunning}
                className="w-full px-4 py-3 bg-gradient-to-r from-indigo-600 to-purple-600 text-white rounded-2xl font-medium hover:from-indigo-700 hover:to-purple-700 disabled:from-gray-400 disabled:to-gray-400 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2 shadow-lg shadow-indigo-200"
            >
                {isRunning ? (
                    <>
                        <RefreshCw className="w-5 h-5 animate-spin" />
                        <span>优化进行中...</span>
                    </>
                ) : (
                    <>
                        <Settings className="w-5 h-5" />
                        <span>启动遗传算法优化</span>
                    </>
                )}
            </button>
        </div>
    );
};

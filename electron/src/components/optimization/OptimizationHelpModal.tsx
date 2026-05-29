import React from 'react';
import { X, HelpCircle, Grid, Zap, Target } from 'lucide-react';

interface Props {
    isOpen: boolean;
    onClose: () => void;
}

export const OptimizationHelpModal: React.FC<Props> = ({ isOpen, onClose }) => {
    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-in fade-in duration-200">
            <div className="bg-white rounded-2xl shadow-2xl w-full max-w-3xl max-h-[90vh] overflow-hidden flex flex-col animate-in zoom-in-95 duration-200">

                {/* Header */}
                <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 bg-gradient-to-r from-blue-50 to-indigo-50">
                    <div className="flex items-center gap-2 text-indigo-900">
                        <HelpCircle className="w-5 h-5" />
                        <h2 className="text-lg font-bold">参数优化实验室使用指南</h2>
                    </div>
                    <button
                        onClick={onClose}
                        className="p-2 text-gray-500 hover:text-gray-700 hover:bg-white/50 rounded-full transition-colors"
                    >
                        <X className="w-5 h-5" />
                    </button>
                </div>

                {/* Content */}
                <div className="flex-1 overflow-y-auto p-6 space-y-8">

                    {/* Introduction */}
                    <div className="text-gray-600 leading-relaxed">
                        <p>
                            当前版本参数优化实验室仅支持 <strong>网格搜索 (Grid Search)</strong>，
                            适用于 TopkDropout 策略的基础调参场景。
                        </p>
                    </div>

                    {/* Mode Card */}
                    <div className="grid md:grid-cols-1 gap-6">

                        {/* Grid Search Card */}
                        <div className="bg-blue-50/50 border border-blue-100 rounded-xl p-5 hover:shadow-md transition-shadow">
                            <div className="flex items-center gap-2 mb-3 text-blue-800">
                                <Grid className="w-5 h-5" />
                                <h3 className="font-bold text-lg">网格搜索 (Grid Search)</h3>
                            </div>
                            <div className="space-y-3">
                                <div className="text-sm font-medium text-blue-700 bg-blue-100/50 px-2 py-1 rounded w-fit">
                                    适用策略: TopkDropoutStrategy
                                </div>
                                <ul className="text-sm text-gray-600 space-y-2 list-disc list-inside">
                                    <li>适合<strong>参数较少</strong>的策略（如 topk, n_drop）</li>
                                    <li><strong>穷举</strong>所有候选参数组合</li>
                                    <li>可在给定搜索空间内找到<strong>最优结果</strong></li>
                                    <li>建议先小范围试探，再逐步扩大参数区间</li>
                                </ul>
                                <div className="mt-4 pt-4 border-t border-blue-100">
                                    <span className="text-xs font-semibold text-blue-900 uppercase tracking-wider">核心参数</span>
                                    <div className="mt-2 flex flex-wrap gap-2">
                                        <span className="px-2 py-1 bg-white border border-blue-200 rounded text-xs text-gray-600">TopK (持仓数)</span>
                                        <span className="px-2 py-1 bg-white border border-blue-200 rounded text-xs text-gray-600">N_Drop (丢弃数)</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Steps */}
                    <div>
                        <h3 className="flex items-center gap-2 font-bold text-gray-900 mb-4">
                            <Target className="w-5 h-5 text-gray-700" />
                            推荐操作流程
                        </h3>
                        <div className="bg-white border border-gray-200 rounded-xl p-4">
                            <ol className="text-sm text-gray-700 space-y-2 list-decimal list-inside">
                                <li>先设定小范围参数区间（例如 `topk: 20~40`，`n_drop: 2~8`）。</li>
                                <li>点击开始网格搜索，观察最优参数与目标值变化。</li>
                                <li>若结果稳定，再按步长逐步扩大搜索范围做二次优化。</li>
                                <li>确认最优参数后，使用“一键回填”进入回测验证。</li>
                            </ol>
                        </div>
                    </div>

                    {/* Tip */}
                    <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex gap-3 items-start">
                        <Zap className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
                        <div className="text-sm text-amber-800">
                            <strong>当前限制：</strong> 参数优化实验室仅开放 <strong>Grid Search</strong>。
                            遗传算法等高级模式暂未开放，请以网格搜索结果作为当前版本的主要调参依据。
                        </div>
                    </div>

                </div>

                {/* Footer */}
                <div className="px-6 py-4 border-t border-gray-100 bg-gray-50 flex justify-end">
                    <button
                        onClick={onClose}
                        className="px-6 py-2 bg-indigo-600 text-white rounded-xl hover:bg-indigo-700 transition w-full sm:w-auto font-medium shadow-sm shadow-indigo-200"
                    >
                        我明白了
                    </button>
                </div>
            </div>
        </div>
    );
};

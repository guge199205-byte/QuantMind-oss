import React, { useState } from 'react';
import { GridSearchPanel } from './GridSearchPanel';
import { OptimizationHelpModal } from './OptimizationHelpModal';
import { HelpCircle, FlaskConical } from 'lucide-react';

export const ParameterOptimization: React.FC = () => {
  const [isHelpOpen, setIsHelpOpen] = useState(false);

  return (
    <div className="h-full flex flex-col relative">
      <div className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between shrink-0">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">参数优化（Beta）</h1>
          <p className="text-sm text-gray-500 mt-1">
            受限可用模式：仅开放稳定网格搜索，默认服务于 Top-K 策略调参
          </p>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6 relative">
        <div className="max-w-7xl mx-auto pb-20">
          <div className="bg-amber-50 border border-amber-200 rounded-2xl p-4 mb-6">
            <div className="flex items-start gap-3">
              <FlaskConical className="w-5 h-5 text-amber-700 mt-0.5" />
              <div className="text-sm text-amber-900 leading-6">
                <div className="font-semibold">当前为 Beta 受限版</div>
                <div>1. 仅支持 Top-K 参数（topk / n_drop）网格搜索</div>
                <div>2. 默认限制组合规模，避免长时间占用队列</div>
                <div>3. 仅在引擎与队列可用时允许启动优化</div>
              </div>
            </div>
          </div>
          <GridSearchPanel />
        </div>
      </div>

      <button
        onClick={() => setIsHelpOpen(true)}
        className="absolute bottom-8 right-8 p-4 bg-white text-indigo-600 rounded-full shadow-lg hover:shadow-xl hover:bg-gray-50 transition-all z-20 border border-gray-100 group"
        title="查看帮助文档"
      >
        <HelpCircle className="w-6 h-6 group-hover:scale-110 transition-transform" />
      </button>

      <OptimizationHelpModal
        isOpen={isHelpOpen}
        onClose={() => setIsHelpOpen(false)}
      />
    </div>
  );
};

import React from 'react';
import { Info } from 'lucide-react';

export const QlibInfoBanner: React.FC = () => (
  <div className="mb-4 bg-blue-50 border border-blue-200 rounded-2xl p-4">
    <div className="flex items-center gap-2 mb-2">
      <Info className="h-4 w-4 text-blue-600" />
      <h4 className="font-medium text-blue-900">Qlib 回测引擎 - 真实数据 & 真实费率</h4>
    </div>
    <div className="text-sm text-blue-700">
      <ul className="list-disc list-inside space-y-1">
        <li>默认范围以当前回测中心配置为准，支持在界面中显式调整开始 / 结束日期</li>
        <li>支持股票范围与数据覆盖会随后端数据源动态变化</li>
        <li>回测频率: 日频</li>
        <li>策略类型: Top-K / 权重 / 多空 / 自定义 Qlib 策略 (可配置参数)</li>
        <li>基准指数: 沪深300 (SH000300)</li>
        <li className="font-medium">
          交易费率（按成交金额比例收取）:
          <ul className="list-none ml-6 mt-1 space-y-0.5 text-xs">
            <li>• 买入: 成交金额 × 0.026% (佣金2.5 + 过户费0.1)</li>
            <li>• 卖出: 成交金额 × 0.076% (佣金2.5 + 过户费0.1 + 印花税5.0)</li>
            <li>• 示例: 10万元交易，买入26元，卖出76元，合计102元</li>
          </ul>
        </li>
      </ul>
    </div>
  </div>
);

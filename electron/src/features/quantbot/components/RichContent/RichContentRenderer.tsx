/**
 * 富文本渲染器 - 根据消息类型渲染不同的内容
 */

import React from 'react';
import FinancialCard, { FinancialCardProps } from './FinancialCard';
import StockQuoteCard, { StockQuoteProps } from './StockQuoteCard';
import TrendChart, { TrendChartProps } from './TrendChart';
import KLineChart, { KLineChartProps } from './KLineChart';

export type RichContentType =
  | 'financial_card'
  | 'stock_quote'
  | 'trend_chart'
  | 'kline_chart'
  | 'text'
  | 'code'
  | 'table';

export interface RichContentData {
  type: RichContentType;
  data: any;
}

export interface RichContentRendererProps {
  content: RichContentData;
}

const RichContentRenderer: React.FC<RichContentRendererProps> = ({ content }) => {
  switch (content.type) {
    case 'financial_card':
      return <FinancialCard {...(content.data as FinancialCardProps)} />;

    case 'stock_quote':
      return <StockQuoteCard {...(content.data as StockQuoteProps)} />;

    case 'trend_chart':
      return <TrendChart {...(content.data as TrendChartProps)} />;

    case 'kline_chart':
      return <KLineChart {...(content.data as KLineChartProps)} />;

    case 'code':
      return (
        <div className="bg-gray-900 rounded-lg p-4 overflow-x-auto">
          <pre className="text-sm text-gray-100">
            <code>{content.data.code}</code>
          </pre>
        </div>
      );

    case 'table':
      return (
        <div className="overflow-x-auto bg-white rounded-lg border border-gray-200">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                {content.data.headers?.map((header: string, idx: number) => (
                  <th
                    key={idx}
                    className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                  >
                    {header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {content.data.rows?.map((row: any[], rowIdx: number) => (
                <tr key={rowIdx} className="hover:bg-gray-50">
                  {row.map((cell, cellIdx) => (
                    <td
                      key={cellIdx}
                      className="px-4 py-3 whitespace-nowrap text-sm text-gray-900"
                    >
                      {cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );

    case 'text':
    default:
      return (
        <div className="prose prose-sm max-w-none">
          <p className="text-gray-700 whitespace-pre-wrap">{content.data.text}</p>
        </div>
      );
  }
};

export default RichContentRenderer;

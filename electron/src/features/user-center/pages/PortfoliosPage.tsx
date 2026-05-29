/**
 * 投资组合页面
 */

import React, { useState } from 'react';
import { usePortfolios } from '../hooks';
import { Card, List, Button, Spin, Alert, Empty, Progress } from 'antd';
import { PlusOutlined, FundOutlined } from '@ant-design/icons';
import PortfolioCreateModal from '../components/PortfolioCreateModal';

interface PortfoliosPageProps {
  userId: string;
}

import { Plus, LayoutGrid, PieChart, ArrowRight, RefreshCw } from 'lucide-react';

const PortfoliosPage: React.FC<PortfoliosPageProps> = ({ userId }) => {
  const { portfolios, isLoading, error, refetch } = usePortfolios(userId);
  const [createModalVisible, setCreateModalVisible] = useState(false);

  if (isLoading) {
    return (
      <div className="flex flex-col items-center gap-4 py-24">
         <RefreshCw className="w-8 h-8 animate-spin text-blue-500 opacity-20" />
         <p className="text-sm font-bold text-gray-400 uppercase tracking-widest">Loading Portfolios...</p>
      </div>
    );
  }

  if (error) {
    return <Alert message="错误" description={error} type="error" showIcon className="rounded-xl" />;
  }

  const handleCreateSuccess = () => {
    setCreateModalVisible(false);
    refetch();
  };

  if (!portfolios || portfolios.length === 0) {
    return (
      <div className="bg-white rounded-2xl border border-gray-100 p-24 text-center">
        <Empty
          description={<span className="text-slate-400 font-medium">您还没有创建任何投资组合</span>}
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        >
          <button
            onClick={() => setCreateModalVisible(true)}
            className="flex items-center gap-2 px-8 py-3 bg-gradient-to-r from-blue-500 to-purple-600 text-white rounded-xl font-black text-sm shadow-lg shadow-blue-500/20 mx-auto"
          >
            <Plus className="w-4 h-4" />
            <span>立即创建第一个组合</span>
          </button>
        </Empty>
        <PortfolioCreateModal
          visible={createModalVisible}
          onCancel={() => setCreateModalVisible(false)}
          onSuccess={handleCreateSuccess}
          userId={userId}
        />
      </div>
    );
  }

  return (
    <div className="portfolios-page">
      <div className="mb-8 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <LayoutGrid className="w-5 h-5 text-blue-500" />
          <h2 className="text-xl font-black text-slate-800 tracking-tight">我的投资组合</h2>
        </div>
        <button
          onClick={() => setCreateModalVisible(true)}
          className="flex items-center gap-2 px-6 py-2 bg-gradient-to-r from-blue-500 to-purple-600 text-white rounded-xl font-black text-sm shadow-md hover:shadow-lg transition-all active:scale-95"
        >
          <Plus className="w-4 h-4" />
          <span>创建新组合</span>
        </button>
      </div>

      <List
        grid={{
          gutter: 24,
          xs: 1,
          sm: 2,
          md: 2,
          lg: 3,
          xl: 3,
          xxl: 4,
        }}
        dataSource={portfolios}
        renderItem={(portfolio: any) => {
          const returnPct = portfolio.total_return_pct || 0;
          const isProfit = returnPct >= 0;

          return (
            <List.Item>
              <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6 transition-all hover:border-blue-200 hover:shadow-md group">
                <div className="flex items-start justify-between mb-6">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-blue-50 flex items-center justify-center">
                      <PieChart className="w-5 h-5 text-blue-500" />
                    </div>
                    <div>
                      <h3 className="font-black text-slate-800 leading-tight">{portfolio.portfolio_name}</h3>
                      <p className="text-[10px] text-gray-400 font-bold uppercase mt-0.5 truncate max-w-[120px]">{portfolio.description || 'Global Strategy'}</p>
                    </div>
                  </div>
                  <span className={`text-xs font-black px-2 py-0.5 rounded-lg border ${isProfit ? 'bg-emerald-50 text-emerald-600 border-emerald-100' : 'bg-rose-50 text-rose-600 border-rose-100'}`}>
                    {isProfit ? '+' : ''}{returnPct.toFixed(2)}%
                  </span>
                </div>

                <div className="space-y-3 mb-8">
                  <div className="flex justify-between items-end">
                    <span className="text-[10px] text-gray-400 font-black uppercase tracking-widest">Total Value</span>
                    <span className="text-base font-black text-slate-800 font-mono">¥{portfolio.total_value?.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between items-end">
                    <span className="text-[10px] text-gray-400 font-black uppercase tracking-widest">Cash Balance</span>
                    <span className="text-sm font-bold text-slate-600 font-mono">¥{portfolio.cash_balance?.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between items-end pt-2 border-t border-gray-50">
                    <span className="text-[10px] text-gray-400 font-black uppercase tracking-widest">Net Return</span>
                    <span className={`text-sm font-black font-mono ${isProfit ? 'text-emerald-500' : 'text-rose-500'}`}>
                      ¥{portfolio.total_return?.toLocaleString()}
                    </span>
                  </div>
                </div>

                {portfolio.positions && portfolio.positions.length > 0 && (
                  <div className="bg-slate-50/50 rounded-xl p-4 border border-slate-100 mb-6">
                    <div className="text-[9px] font-black text-slate-400 uppercase tracking-widest mb-3">Asset Allocation ({portfolio.positions.length})</div>
                    <div className="space-y-2">
                      {portfolio.positions.slice(0, 3).map((pos, idx) => (
                        <div key={idx} className="flex items-center gap-3">
                          <span className="text-[10px] font-bold text-slate-600 w-12">{pos.symbol}</span>
                          <div className="flex-1 h-1.5 bg-slate-200 rounded-full overflow-hidden">
                            <div className="h-full bg-blue-500 rounded-full" style={{ width: `${Math.min(pos.weight, 100)}%` }} />
                          </div>
                          <span className="text-[10px] font-black text-slate-400 w-8 text-right">{pos.weight}%</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <button className="w-full flex items-center justify-center gap-2 py-2.5 text-[11px] font-black text-blue-500 hover:text-blue-600 uppercase tracking-widest transition-all">
                  View Portfolio Details <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </div>
            </List.Item>
          );
        }}
      />

      <PortfolioCreateModal
        visible={createModalVisible}
        onCancel={() => setCreateModalVisible(false)}
        onSuccess={handleCreateSuccess}
        userId={userId}
      />
    </div>
  );
};

export default PortfoliosPage;

/**
 * 交易记录列表组件
 * 展示回测的所有交易记录
 */

import React, { useState, useMemo } from 'react';
import { Trade } from '../../types/backtest';

interface TradeListProps {
  trades: Trade[];
}

type SortField = 'timestamp' | 'price' | 'size' | 'pnl';
type SortOrder = 'asc' | 'desc';

export const TradeList: React.FC<TradeListProps> = ({ trades }) => {
  const [sortField, setSortField] = useState<SortField>('timestamp');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');
  const [filter, setFilter] = useState<'all' | 'buy' | 'sell' | 'profit' | 'loss'>('all');
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 20;

  // 过滤和排序
  const filteredTrades = useMemo(() => {
    let result = [...trades];

    // 过滤
    switch (filter) {
      case 'buy':
        result = result.filter(t => t.side === 'buy');
        break;
      case 'sell':
        result = result.filter(t => t.side === 'sell');
        break;
      case 'profit':
        result = result.filter(t => t.pnl && t.pnl > 0);
        break;
      case 'loss':
        result = result.filter(t => t.pnl && t.pnl < 0);
        break;
    }

    // 排序
    result.sort((a, b) => {
      let aValue: any, bValue: any;

      switch (sortField) {
        case 'timestamp':
          aValue = a.timestamp;
          bValue = b.timestamp;
          break;
        case 'price':
          aValue = a.price;
          bValue = b.price;
          break;
        case 'size':
          aValue = a.size;
          bValue = b.size;
          break;
        case 'pnl':
          aValue = a.pnl || 0;
          bValue = b.pnl || 0;
          break;
      }

      return sortOrder === 'asc' ? aValue - bValue : bValue - aValue;
    });

    return result;
  }, [trades, sortField, sortOrder, filter]);

  // 分页
  const totalPages = Math.ceil(filteredTrades.length / itemsPerPage);
  const paginatedTrades = useMemo(() => {
    const start = (currentPage - 1) * itemsPerPage;
    return filteredTrades.slice(start, start + itemsPerPage);
  }, [filteredTrades, currentPage]);

  // 处理排序
  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortOrder('desc');
    }
  };

  // 格式化时间
  const formatTime = (timestamp: number) => {
    return new Date(timestamp).toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });
  };

  // 统计信息
  const stats = useMemo(() => {
    const closedTrades = trades.filter(t => t.pnl !== undefined);
    const winTrades = closedTrades.filter(t => t.pnl! > 0);
    const lossTrades = closedTrades.filter(t => t.pnl! < 0);

    return {
      total: trades.length,
      closed: closedTrades.length,
      wins: winTrades.length,
      losses: lossTrades.length,
      winRate: closedTrades.length > 0 ? (winTrades.length / closedTrades.length * 100) : 0,
      totalPnL: closedTrades.reduce((sum, t) => sum + (t.pnl || 0), 0),
      totalCommission: trades.reduce((sum, t) => sum + t.commission, 0),
      totalSlippage: trades.reduce((sum, t) => sum + t.slippage, 0)
    };
  }, [trades]);

  return (
    <div className="trade-list">
      <div className="list-header">
        <h3>交易记录</h3>

        {/* 统计卡片 */}
        <div className="trade-stats">
          <div className="stat-card">
            <span className="stat-label">总交易数</span>
            <span className="stat-value">{stats.total}</span>
          </div>
          <div className="stat-card">
            <span className="stat-label">完成交易</span>
            <span className="stat-value">{stats.closed}</span>
          </div>
          <div className="stat-card">
            <span className="stat-label">胜率</span>
            <span className="stat-value positive">{stats.winRate.toFixed(1)}%</span>
          </div>
          <div className="stat-card">
            <span className="stat-label">总盈亏</span>
            <span className={`stat-value ${stats.totalPnL >= 0 ? 'positive' : 'negative'}`}>
              ${stats.totalPnL.toFixed(2)}
            </span>
          </div>
        </div>
      </div>

      {/* 过滤器 */}
      <div className="list-filters">
        <button
          className={`filter-btn ${filter === 'all' ? 'active' : ''}`}
          onClick={() => setFilter('all')}
        >
          全部 ({trades.length})
        </button>
        <button
          className={`filter-btn ${filter === 'buy' ? 'active' : ''}`}
          onClick={() => setFilter('buy')}
        >
          买入
        </button>
        <button
          className={`filter-btn ${filter === 'sell' ? 'active' : ''}`}
          onClick={() => setFilter('sell')}
        >
          卖出
        </button>
        <button
          className={`filter-btn ${filter === 'profit' ? 'active' : ''}`}
          onClick={() => setFilter('profit')}
        >
          盈利
        </button>
        <button
          className={`filter-btn ${filter === 'loss' ? 'active' : ''}`}
          onClick={() => setFilter('loss')}
        >
          亏损
        </button>
      </div>

      {/* 交易表格 */}
      <div className="trade-table-container">
        <table className="trade-table">
          <thead>
            <tr>
              <th onClick={() => handleSort('timestamp')}>
                时间 {sortField === 'timestamp' && (sortOrder === 'asc' ? '↑' : '↓')}
              </th>
              <th>方向</th>
              <th onClick={() => handleSort('price')}>
                价格 {sortField === 'price' && (sortOrder === 'asc' ? '↑' : '↓')}
              </th>
              <th onClick={() => handleSort('size')}>
                数量 {sortField === 'size' && (sortOrder === 'asc' ? '↑' : '↓')}
              </th>
              <th>手续费</th>
              <th>滑点</th>
              <th onClick={() => handleSort('pnl')}>
                盈亏 {sortField === 'pnl' && (sortOrder === 'asc' ? '↑' : '↓')}
              </th>
              <th>累计盈亏</th>
            </tr>
          </thead>
          <tbody>
            {paginatedTrades.map(trade => (
              <tr key={trade.id}>
                <td className="time-cell">{formatTime(trade.timestamp)}</td>
                <td>
                  <span className={`side-badge ${trade.side}`}>
                    {trade.side === 'buy' ? '买入' : '卖出'}
                  </span>
                </td>
                <td className="price-cell">${trade.price.toFixed(2)}</td>
                <td className="size-cell">{trade.size}</td>
                <td className="commission-cell">${trade.commission.toFixed(2)}</td>
                <td className="slippage-cell">${trade.slippage.toFixed(2)}</td>
                <td className={`pnl-cell ${trade.pnl ? (trade.pnl >= 0 ? 'positive' : 'negative') : ''}`}>
                  {trade.pnl !== undefined ? `$${trade.pnl.toFixed(2)}` : '-'}
                </td>
                <td className={`cumulative-pnl-cell ${trade.cumulativePnL ? (trade.cumulativePnL >= 0 ? 'positive' : 'negative') : ''}`}>
                  {trade.cumulativePnL !== undefined ? `$${trade.cumulativePnL.toFixed(2)}` : '-'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* 分页 */}
      {totalPages > 1 && (
        <div className="pagination">
          <button
            className="page-btn"
            onClick={() => (setCurrentPage as any)((p: number) => Math.max(1, p - 1))}
            disabled={currentPage === 1}
          >
            上一页
          </button>
          <span className="page-info">
            第 {currentPage} / {totalPages} 页 (共 {filteredTrades.length} 条)
          </span>
          <button
            className="page-btn"
            onClick={() => (setCurrentPage as any)((p: number) => Math.min(totalPages, p + 1))}
            disabled={currentPage === totalPages}
          >
            下一页
          </button>
        </div>
      )}

      <style>{`
        .trade-list {
          background: #252526;
          border-radius: 8px;
          padding: 16px;
          margin-bottom: 16px;
        }

        .list-header {
          margin-bottom: 20px;
        }

        .list-header h3 {
          margin: 0 0 16px 0;
          color: #d4d4d4;
          font-size: 18px;
        }

        .trade-stats {
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          gap: 12px;
        }

        .stat-card {
          background: #1e1e1e;
          padding: 12px;
          border-radius: 6px;
          display: flex;
          flex-direction: column;
          gap: 6px;
        }

        .stat-label {
          font-size: 12px;
          color: #969696;
        }

        .stat-value {
          font-size: 20px;
          font-weight: 600;
          color: #d4d4d4;
        }

        .stat-value.positive {
          color: #26a269;
        }

        .stat-value.negative {
          color: #f66151;
        }

        .list-filters {
          display: flex;
          gap: 8px;
          margin-bottom: 16px;
        }

        .filter-btn {
          padding: 8px 16px;
          background: #3c3c3c;
          color: #d4d4d4;
          border: 1px solid #555;
          border-radius: 4px;
          cursor: pointer;
          font-size: 13px;
          transition: all 0.2s;
        }

        .filter-btn:hover {
          background: #4a4a4a;
        }

        .filter-btn.active {
          background: #0e639c;
          border-color: #0e639c;
          color: white;
        }

        .trade-table-container {
          overflow-x: auto;
          margin-bottom: 16px;
        }

        .trade-table {
          width: 100%;
          border-collapse: collapse;
          font-size: 13px;
        }

        .trade-table th {
          background: #1e1e1e;
          color: #969696;
          font-weight: 600;
          text-align: left;
          padding: 12px;
          border-bottom: 2px solid #3e3e42;
          cursor: pointer;
          user-select: none;
        }

        .trade-table th:hover {
          background: #2a2a2a;
        }

        .trade-table td {
          padding: 10px 12px;
          border-bottom: 1px solid #3e3e42;
          color: #d4d4d4;
        }

        .trade-table tbody tr:hover {
          background: #2a2a2a;
        }

        .time-cell {
          font-family: var(--font-mono);
          font-size: 12px;
        }

        .side-badge {
          padding: 4px 8px;
          border-radius: 4px;
          font-size: 11px;
          font-weight: 600;
          display: inline-block;
        }

        .side-badge.buy {
          background: #26a2691a;
          color: #26a269;
        }

        .side-badge.sell {
          background: #f661511a;
          color: #f66151;
        }

        .price-cell,
        .size-cell,
        .commission-cell,
        .slippage-cell {
          font-family: var(--font-mono);
        }

        .pnl-cell,
        .cumulative-pnl-cell {
          font-family: var(--font-mono);
          font-weight: 600;
        }

        .pnl-cell.positive,
        .cumulative-pnl-cell.positive {
          color: #26a269;
        }

        .pnl-cell.negative,
        .cumulative-pnl-cell.negative {
          color: #f66151;
        }

        .pagination {
          display: flex;
          justify-content: center;
          align-items: center;
          gap: 16px;
        }

        .page-btn {
          padding: 8px 16px;
          background: #3c3c3c;
          color: #d4d4d4;
          border: 1px solid #555;
          border-radius: 4px;
          cursor: pointer;
          font-size: 13px;
        }

        .page-btn:hover:not(:disabled) {
          background: #4a4a4a;
        }

        .page-btn:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .page-info {
          color: #969696;
          font-size: 13px;
        }
      `}</style>
    </div>
  );
};

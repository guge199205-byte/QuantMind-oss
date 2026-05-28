/** Analysis history list */

import React from 'react';
import type { AnalysisHistoryItem } from '../types';

interface HistoryListProps {
  history: AnalysisHistoryItem[];
  onSelect: (item: AnalysisHistoryItem) => void;
}

function signalColor(signal: string): string {
  const s = (signal || '').toUpperCase();
  if (s.includes('BUY')) return '#16a34a';
  if (s.includes('SELL')) return '#ef4444';
  return '#d97706';
}

export const HistoryList: React.FC<HistoryListProps> = ({ history, onSelect }) => {
  if (!history.length) {
    return (
      <div style={{ color: '#94a3b8', fontSize: 13, textAlign: 'center', padding: 20 }}>
        暂无历史记录
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      {history.map((item) => (
        <button
          key={item.analysis_id}
          onClick={() => onSelect(item)}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '10px 12px',
            background: '#fff',
            border: '1px solid #e2e8f0',
            borderRadius: 8,
            cursor: 'pointer',
            transition: 'all 0.2s',
            color: '#1e293b',
            fontSize: 13,
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.borderColor = '#ff5a1f';
            e.currentTarget.style.background = '#fff7ed';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.borderColor = '#e2e8f0';
            e.currentTarget.style.background = '#fff';
          }}
        >
          <span style={{ fontWeight: 600 }}>{item.ticker}</span>
          <span style={{ color: '#94a3b8', fontSize: 12 }}>{item.trade_date}</span>
          {item.signal && (
            <span style={{
              color: signalColor(item.signal),
              fontSize: 12,
              fontWeight: 700,
            }}>
              {item.signal.toUpperCase()}
            </span>
          )}
        </button>
      ))}
    </div>
  );
};

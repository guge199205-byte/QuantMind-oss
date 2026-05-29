/** Analysis history list */

import React from 'react';
import type { AnalysisHistoryItem } from '../types';
import { getDownloadUrl } from '../services/tradingAgentsService';

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
        <div
          key={item.analysis_id}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: '10px 12px',
            background: '#fff',
            border: '1px solid #e2e8f0',
            borderRadius: 8,
            transition: 'all 0.2s',
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
          <button
            onClick={() => onSelect(item)}
            style={{
              flex: 1,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              color: '#1e293b',
              fontSize: 13,
              padding: 0,
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
          <a
            href={getDownloadUrl(item.analysis_id)}
            download
            title="下载报告"
            style={{
              color: '#94a3b8',
              fontSize: 14,
              textDecoration: 'none',
              padding: '2px 4px',
              borderRadius: 4,
              lineHeight: 1,
            }}
            onClick={(e) => e.stopPropagation()}
            onMouseEnter={(e) => { e.currentTarget.style.color = '#ff5a1f'; }}
            onMouseLeave={(e) => { e.currentTarget.style.color = '#94a3b8'; }}
          >
            ↓
          </a>
        </div>
      ))}
    </div>
  );
};

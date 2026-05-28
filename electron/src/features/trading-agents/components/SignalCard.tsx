/** Trading signal card — BUY / HOLD / SELL */

import React from 'react';

interface SignalCardProps {
  signal: string;
  ticker: string;
  tradeDate: string;
  elapsed?: number;
}

function signalStyle(signal: string): { color: string; label: string; bg: string } {
  const s = signal.toUpperCase();
  if (s.includes('BUY')) return { color: '#16a34a', label: '买入', bg: '#ecfdf5' };
  if (s.includes('SELL')) return { color: '#ef4444', label: '卖出', bg: '#fef2f2' };
  return { color: '#d97706', label: '持有', bg: '#fffbeb' };
}

export const SignalCard: React.FC<SignalCardProps> = ({
  signal,
  ticker,
  tradeDate,
  elapsed,
}) => {
  const { color, label, bg } = signalStyle(signal);
  const elapsedStr = elapsed != null
    ? `${Math.floor(elapsed / 60)}:${Math.floor(elapsed % 60).toString().padStart(2, '0')}`
    : '';

  return (
    <div style={{
      background: 'rgba(255,255,255,0.9)',
      border: '1px solid #e2e8f0',
      borderRadius: 16,
      padding: '2rem',
      textAlign: 'center',
      margin: '0 0 2rem',
      backdropFilter: 'blur(8px)',
    }}>
      <div style={{ fontSize: 13, color: '#94a3b8', letterSpacing: 2 }}>TRADING SIGNAL</div>
      <div style={{
        fontSize: 56,
        fontWeight: 900,
        color,
        margin: '6px 0',
      }}>
        {signal.toUpperCase()}
      </div>
      <div style={{ fontSize: 16, color: '#1e293b' }}>
        {ticker} · {tradeDate}
        {elapsedStr && (
          <span style={{ fontSize: 13, color: '#94a3b8', marginLeft: 12 }}>
            耗时 {elapsedStr}
          </span>
        )}
      </div>
      <div style={{
        marginTop: 12,
        padding: '6px 16px',
        display: 'inline-block',
        borderRadius: 20,
        background: bg,
        border: `1px solid ${color}40`,
        color,
        fontSize: 14,
        fontWeight: 600,
      }}>
        {label}
      </div>
      <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 10 }}>
        本报告由 AI 自动生成，仅供学习研究，不构成投资建议。
      </div>
    </div>
  );
};

/** Stock input with date picker */

import React from 'react';

interface StockInputProps {
  ticker: string;
  tradeDate: string;
  disabled?: boolean;
  onTickerChange: (v: string) => void;
  onDateChange: (v: string) => void;
}

const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '10px 12px',
  background: '#fff',
  border: '1px solid #e2e8f0',
  borderRadius: 8,
  color: '#1e293b',
  fontSize: 14,
  outline: 'none',
  transition: 'border-color 0.2s',
};

export const StockInput: React.FC<StockInputProps> = ({
  ticker,
  tradeDate,
  disabled,
  onTickerChange,
  onDateChange,
}) => (
  <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
    <div>
      <label style={{ display: 'block', fontSize: 13, color: '#64748b', marginBottom: 4 }}>
        股票代码
      </label>
      <input
        type="text"
        value={ticker}
        onChange={(e) => onTickerChange(e.target.value)}
        placeholder="例: 300750 或 宁德时代"
        disabled={disabled}
        style={inputStyle}
      />
    </div>
    <div>
      <label style={{ display: 'block', fontSize: 13, color: '#64748b', marginBottom: 4 }}>
        分析日期
      </label>
      <input
        type="date"
        value={tradeDate}
        onChange={(e) => onDateChange(e.target.value)}
        disabled={disabled}
        style={inputStyle}
      />
    </div>
  </div>
);

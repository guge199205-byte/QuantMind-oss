import { useState, useEffect } from 'react';
import { alphaAgentService, EvolutionStats } from '../services/alphaAgentService';

export function EvolutionStatsPanel() {
  const [stats, setStats] = useState<EvolutionStats | null>(null);

  useEffect(() => {
    alphaAgentService.getStats().then(setStats).catch(() => {});
    const iv = setInterval(() => {
      alphaAgentService.getStats().then(setStats).catch(() => {});
    }, 30000);
    return () => clearInterval(iv);
  }, []);

  if (!stats) {
    return (
      <div style={{ padding: 16, color: '#666', fontSize: 13, textAlign: 'center' }}>
        加载统计...
      </div>
    );
  }

  const items = [
    { label: '总因子', value: stats.total, color: '#eee' },
    { label: '已完成', value: stats.completed, color: '#4CAF50' },
    { label: '回测中', value: stats.backtesting, color: '#FF9800' },
    { label: '待处理', value: stats.pending, color: '#888' },
    { label: '失败', value: stats.failed, color: '#f44336' },
    { label: '平均IC', value: stats.avg_ic?.toFixed(4), color: '#2196F3' },
    { label: '最高IC', value: stats.best_ic?.toFixed(4), color: '#2196F3' },
    { label: '平均Sharpe', value: stats.avg_sharpe?.toFixed(2), color: '#9C27B0' },
    { label: '最高Sharpe', value: stats.best_sharpe?.toFixed(2), color: '#9C27B0' },
  ];

  return (
    <div style={{ padding: 16 }}>
      <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600, marginBottom: 10 }}>
        演化统计
      </h3>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 6 }}>
        {items.map((item) => (
          <div
            key={item.label}
            style={{
              padding: '6px 8px',
              borderRadius: 6,
              background: '#1a1a2e',
              textAlign: 'center',
            }}
          >
            <div style={{ fontSize: 10, color: '#888' }}>{item.label}</div>
            <div style={{ fontSize: 14, fontWeight: 600, color: item.color }}>
              {item.value ?? '—'}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
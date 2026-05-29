import { useState, useEffect, useCallback } from 'react';
import { alphaAgentService, AlphaFactor } from '../services/alphaAgentService';

interface Props {
  userId: string;
  selectedFactorId: string | null;
  onSelect: (id: string) => void;
}

export function FactorListPanel({ userId, selectedFactorId, onSelect }: Props) {
  const [factors, setFactors] = useState<AlphaFactor[]>([]);
  const [filter, setFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const list = await alphaAgentService.listFactors({
        userId,
        status: statusFilter || undefined,
        limit: 100,
      });
      setFactors(list);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [userId, statusFilter]);

  useEffect(() => {
    refresh();
    const iv = setInterval(refresh, 15000);
    return () => clearInterval(iv);
  }, [refresh]);

  const filtered = factors.filter((f) => {
    if (!filter) return true;
    const q = filter.toLowerCase();
    return (
      f.factor_name.toLowerCase().includes(q) ||
      f.category?.toLowerCase().includes(q) ||
      f.factor_formulation?.toLowerCase().includes(q)
    );
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', padding: 16 }}>
      <h3 style={{ margin: 0, fontSize: 16, fontWeight: 600, marginBottom: 12 }}>因子列表</h3>

      <input
        type="text"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        placeholder="搜索因子..."
        style={{
          padding: '6px 10px',
          borderRadius: 6,
          border: '1px solid #333',
          background: '#1a1a2e',
          color: '#eee',
          fontSize: 12,
          marginBottom: 8,
        }}
      />

      <div style={{ display: 'flex', gap: 4, marginBottom: 8, flexWrap: 'wrap' }}>
        {['', 'completed', 'pending', 'backtesting', 'failed'].map((s) => (
          <button
            key={s}
            onClick={() => setStatusFilter(s)}
            style={{
              padding: '2px 8px',
              borderRadius: 4,
              border: statusFilter === s ? '1px solid #4CAF50' : '1px solid #333',
              background: statusFilter === s ? '#4CAF5020' : 'transparent',
              color: statusFilter === s ? '#4CAF50' : '#888',
              fontSize: 11,
              cursor: 'pointer',
            }}
          >
            {s || '全部'}
          </button>
        ))}
      </div>

      <div style={{ flex: 1, overflow: 'auto', display: 'flex', flexDirection: 'column', gap: 4 }}>
        {loading && factors.length === 0 && (
          <div style={{ color: '#666', fontSize: 12, textAlign: 'center', padding: 20 }}>加载中...</div>
        )}
        {!loading && filtered.length === 0 && (
          <div style={{ color: '#666', fontSize: 12, textAlign: 'center', padding: 20 }}>
            暂无因子数据
          </div>
        )}
        {filtered.map((f) => (
          <div
            key={f.id || f.factor_name}
            onClick={() => onSelect(f.id)}
            style={{
              padding: '8px 10px',
              borderRadius: 6,
              background: selectedFactorId === f.id ? '#ffffff10' : '#1a1a2e',
              border: selectedFactorId === f.id ? '1px solid #4CAF50' : '1px solid #222',
              cursor: 'pointer',
              display: 'flex',
              flexDirection: 'column',
              gap: 2,
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: 13, fontWeight: 600, color: '#eee' }}>
                {f.factor_name}
              </span>
              <span style={{ fontSize: 10, color: '#666' }}>{f.category}</span>
            </div>
            <div style={{ display: 'flex', gap: 12, fontSize: 11, color: '#aaa' }}>
              {f.ic_value != null && <span>IC: {f.ic_value.toFixed(4)}</span>}
              {f.sharpe_ratio != null && <span>Sharpe: {f.sharpe_ratio.toFixed(2)}</span>}
              <span style={{ color: '#555' }}>{f.status}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
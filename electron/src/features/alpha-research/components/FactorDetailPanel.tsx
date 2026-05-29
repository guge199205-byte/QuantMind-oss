import { useState, useEffect } from 'react';
import { alphaAgentService, AlphaFactor } from '../services/alphaAgentService';

interface Props {
  factorId: string | null;
}

export function FactorDetailPanel({ factorId }: Props) {
  const [factor, setFactor] = useState<AlphaFactor | null>(null);
  const [loading, setLoading] = useState(false);
  const [backtesting, setBacktesting] = useState(false);

  useEffect(() => {
    if (!factorId) {
      setFactor(null);
      return;
    }
    setLoading(true);
    alphaAgentService
      .getFactor(factorId)
      .then(setFactor)
      .catch(() => setFactor(null))
      .finally(() => setLoading(false));
  }, [factorId]);

  // Auto-refresh when backtesting
  useEffect(() => {
    if (factor?.status !== 'backtesting') return;
    const iv = setInterval(async () => {
      if (!factorId) return;
      try {
        const updated = await alphaAgentService.getFactor(factorId);
        setFactor(updated);
        if (updated.status !== 'backtesting') setBacktesting(false);
      } catch {
        // ignore
      }
    }, 5000);
    return () => clearInterval(iv);
  }, [factorId, factor?.status]);

  const handleBacktest = async () => {
    if (!factorId) return;
    setBacktesting(true);
    try {
      await alphaAgentService.backtestFactor(factorId);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      alert(msg);
      setBacktesting(false);
    }
  };

  if (!factorId) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#666', fontSize: 13 }}>
        选择一个因子查看详情
      </div>
    );
  }

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#888', fontSize: 13 }}>
        加载中...
      </div>
    );
  }

  if (!factor) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#666', fontSize: 13 }}>
        因子不存在
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', padding: 16, gap: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ margin: 0, fontSize: 16, fontWeight: 600, color: '#eee' }}>
          {factor.factor_name}
        </h3>
        <div style={{ display: 'flex', gap: 8 }}>
          <span
            style={{
              padding: '2px 8px',
              borderRadius: 4,
              fontSize: 11,
              background: factor.status === 'completed' ? '#4CAF5020' : '#333',
              color: factor.status === 'completed' ? '#4CAF50' : '#888',
            }}
          >
            {factor.status}
          </span>
          {factor.category && (
            <span
              style={{
                padding: '2px 8px',
                borderRadius: 4,
                fontSize: 11,
                background: '#333',
                color: '#888',
              }}
            >
              {factor.category}
            </span>
          )}
        </div>
      </div>

      {/* Metrics */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(4, 1fr)',
          gap: 8,
        }}
      >
        {[
          { label: 'IC', value: factor.ic_value },
          { label: 'Sharpe', value: factor.sharpe_ratio },
          { label: '年化收益', value: factor.annual_return },
          { label: '回测状态', value: factor.status },
        ].map((m) => (
          <div
            key={m.label}
            style={{
              padding: 8,
              borderRadius: 6,
              background: '#1a1a2e',
              textAlign: 'center',
            }}
          >
            <div style={{ fontSize: 10, color: '#888' }}>{m.label}</div>
            <div style={{ fontSize: 14, fontWeight: 600, color: '#eee' }}>
              {typeof m.value === 'number' ? m.value.toFixed(4) : m.value || '—'}
            </div>
          </div>
        ))}
      </div>

      {/* Formulation */}
      {factor.factor_formulation && (
        <div>
          <div style={{ fontSize: 12, color: '#888', marginBottom: 4 }}>公式描述</div>
          <div
            style={{
              padding: 8,
              borderRadius: 6,
              background: '#1a1a2e',
              fontSize: 12,
              color: '#ccc',
              border: '1px solid #222',
            }}
          >
            {factor.factor_formulation}
          </div>
        </div>
      )}

      {/* Code */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        <div style={{ fontSize: 12, color: '#888', marginBottom: 4 }}>因子代码</div>
        <pre
          style={{
            flex: 1,
            padding: 12,
            borderRadius: 6,
            background: '#0d0d1a',
            fontSize: 12,
            color: '#9CDCFE',
            border: '1px solid #222',
            overflow: 'auto',
            fontFamily: 'monospace',
            lineHeight: 1.5,
            margin: 0,
          }}
        >
          {factor.factor_code || '// 无代码'}
        </pre>
      </div>

      {/* Actions */}
      <div style={{ display: 'flex', gap: 8 }}>
        <button
          onClick={handleBacktest}
          disabled={backtesting || factor.status === 'backtesting'}
          style={{
            padding: '6px 16px',
            borderRadius: 6,
            border: 'none',
            background:
              backtesting || factor.status === 'backtesting' ? '#555' : '#4CAF50',
            color: '#fff',
            fontSize: 12,
            cursor:
              backtesting || factor.status === 'backtesting'
                ? 'not-allowed'
                : 'pointer',
          }}
        >
          {factor.status === 'backtesting' ? '回测中...' : '快速回测'}
        </button>
      </div>
    </div>
  );
}
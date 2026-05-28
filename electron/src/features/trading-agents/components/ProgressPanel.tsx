/** 12-stage pipeline progress panel */

import React from 'react';
import { PIPELINE_STAGES, type AnalysisProgress } from '../types';

interface ProgressPanelProps {
  progress: AnalysisProgress;
}

export const ProgressPanel: React.FC<ProgressPanelProps> = ({ progress }) => {
  const formatElapsed = (sec: number) => {
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  const formatTokens = (n: number) => {
    if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
    if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
    return String(n);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Header */}
      <div style={{ textAlign: 'center' }}>
        <div style={{ fontSize: 13, color: '#64748b', letterSpacing: 2 }}>ANALYSIS IN PROGRESS</div>
        <div style={{ fontSize: 28, fontWeight: 800, color: '#ff5a1f', marginTop: 4 }}>
          {progress.ticker}
        </div>
        <div style={{ fontSize: 14, color: '#94a3b8', marginTop: 2 }}>
          {progress.trade_date}
        </div>
      </div>

      {/* Stage Grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))',
        gap: 10,
      }}>
        {PIPELINE_STAGES.map((stage) => {
          const status = progress.completed_stages.includes(stage.id)
            ? 'done'
            : progress.current_stage === stage.id
            ? 'active'
            : 'pending';

          const bgColor = status === 'done' ? '#ecfdf5' : status === 'active' ? '#fff7ed' : '#f8fafc';
          const borderColor = status === 'done' ? '#86efac' : status === 'active' ? '#ff5a1f' : '#e2e8f0';
          const textColor = status === 'done' ? '#16a34a' : status === 'active' ? '#ff5a1f' : '#94a3b8';

          return (
            <div
              key={stage.id}
              style={{
                background: bgColor,
                border: `1px solid ${borderColor}`,
                borderRadius: 10,
                padding: '12px 10px',
                textAlign: 'center',
                transition: 'all 0.3s ease',
                position: 'relative',
                overflow: 'hidden',
              }}
            >
              <div style={{ fontSize: 22, marginBottom: 4 }}>{stage.icon}</div>
              <div style={{ fontSize: 12, color: textColor, fontWeight: 600 }}>
                {stage.name}
              </div>
              <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 2 }}>
                {status === 'done' ? '✓ 完成' : status === 'active' ? '● 运行中' : '○ 等待'}
              </div>
            </div>
          );
        })}
      </div>

      {/* Stats Bar */}
      <div style={{
        display: 'flex',
        justifyContent: 'center',
        gap: 24,
        padding: '14px 20px',
        background: 'rgba(255,255,255,0.8)',
        borderRadius: 10,
        border: '1px solid #e2e8f0',
        backdropFilter: 'blur(8px)',
      }}>
        <StatItem label="LLM 调用" value={String(progress.stats.llm_calls)} />
        <StatItem label="工具调用" value={String(progress.stats.tool_calls)} />
        <StatItem label="输入 Token" value={formatTokens(progress.stats.tokens_in)} />
        <StatItem label="输出 Token" value={formatTokens(progress.stats.tokens_out)} />
        <StatItem label="耗时" value={formatElapsed(progress.elapsed)} />
      </div>
    </div>
  );
};

const StatItem: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <div style={{ textAlign: 'center' }}>
    <div style={{ fontSize: 18, fontWeight: 700, color: '#ff5a1f' }}>{value}</div>
    <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 2 }}>{label}</div>
  </div>
);

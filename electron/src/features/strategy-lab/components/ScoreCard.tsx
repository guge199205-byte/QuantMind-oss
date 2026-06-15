import React, { useMemo } from 'react';
import { Card, Progress, Tag, Typography, Tooltip } from 'antd';
import type { StrategyLabRunResult } from '../types';

const { Text } = Typography;

interface Props {
  result: StrategyLabRunResult;
  /** Optional 4-gate report from /strategy-lab/overfit-check; rendered if present. */
  overfit?: {
    gate1?: { passed: boolean; score: number; note: string };
    gate2?: { passed: boolean; score: number; note: string };
    gate3?: { passed: boolean; score: number; note: string };
    gate4?: { passed: boolean; score: number; note: string };
    total_score: number;
  } | null;
}

/** Heuristic baseline score so every result has a quick health read. */
function computeQuickScore(result: StrategyLabRunResult): {
  score: number;
  notes: string[];
} {
  const m = result.metrics || ({} as any);
  let score = 0;
  const notes: string[] = [];

  // Sharpe
  if (m.sharpe >= 1.5) {
    score += 30;
    notes.push('夏普 ≥ 1.5：优');
  } else if (m.sharpe >= 1.0) {
    score += 22;
    notes.push('夏普 ≥ 1.0：良');
  } else if (m.sharpe >= 0.5) {
    score += 14;
    notes.push('夏普 0.5-1.0：可');
  } else if (m.sharpe > 0) {
    score += 6;
    notes.push('夏普 > 0：弱');
  } else {
    notes.push('夏普 ≤ 0：警告');
  }

  // 年化
  if (m.annual_return > 0.30) {
    score += 25;
  } else if (m.annual_return > 0.15) {
    score += 18;
  } else if (m.annual_return > 0.08) {
    score += 12;
  } else if (m.annual_return > 0) {
    score += 5;
  } else {
    notes.push('年化收益为负');
  }

  // 回撤
  if (m.max_drawdown > -0.10) {
    score += 25;
    notes.push('回撤 < 10%：稳');
  } else if (m.max_drawdown > -0.20) {
    score += 18;
  } else if (m.max_drawdown > -0.30) {
    score += 10;
  } else {
    notes.push('回撤 > 30%：高风险');
  }

  // 样本量
  if (m.n_trades >= 50) {
    score += 20;
  } else if (m.n_trades >= 20) {
    score += 12;
  } else if (m.n_trades >= 5) {
    score += 6;
    notes.push('交易次数偏少，结论不稳');
  } else {
    notes.push('交易 < 5 次，统计不显著');
  }

  return { score: Math.max(0, Math.min(100, score)), notes };
}

export const ScoreCard: React.FC<Props> = ({ result, overfit }) => {
  const { score, notes } = useMemo(() => computeQuickScore(result), [result]);

  // If overfit gates present, blend their score into final
  const finalScore = useMemo(() => {
    if (!overfit) return score;
    return Math.round(score * 0.6 + (overfit.total_score || 0) * 0.4);
  }, [score, overfit]);

  const status: 'success' | 'normal' | 'exception' =
    finalScore >= 75 ? 'success' : finalScore >= 50 ? 'normal' : 'exception';

  const renderGate = (
    name: string,
    g?: { passed: boolean; score: number; note: string },
  ) => {
    if (!g) return null;
    return (
      <Tooltip title={g.note}>
        <Tag color={g.passed ? 'green' : 'red'} style={{ marginRight: 4 }}>
          {name} {g.score}
        </Tag>
      </Tooltip>
    );
  };

  return (
    <Card size="small" style={{ marginBottom: 8 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
        <div style={{ minWidth: 120 }}>
          <Text strong>策略评分</Text>
          <Progress
            type="dashboard"
            size={70}
            percent={finalScore}
            status={status}
            format={(p) => `${p}`}
          />
        </div>
        <div style={{ flex: 1, minWidth: 200 }}>
          <div style={{ marginBottom: 4 }}>
            {overfit ? (
              <>
                {renderGate('训测', overfit.gate1)}
                {renderGate('走查', overfit.gate2)}
                {renderGate('参敏', overfit.gate3)}
                {renderGate('蒙卡', overfit.gate4)}
              </>
            ) : (
              <Tag color="default">基础启发评分（运行 4 关卡获得过拟合体检）</Tag>
            )}
          </div>
          <ul style={{ margin: 0, paddingLeft: 20, fontSize: 12, color: '#475569' }}>
            {notes.map((n, i) => (
              <li key={i}>{n}</li>
            ))}
          </ul>
        </div>
      </div>
    </Card>
  );
};

export default ScoreCard;

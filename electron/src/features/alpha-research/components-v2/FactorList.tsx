import React, { useState } from 'react';
import {
  AreaChart,
  Area,
  ResponsiveContainer,
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from './ui/Card';
import { HoverCard, HoverCardContent, HoverCardTrigger } from "./ui/HoverCard";
import { RealtimeMetrics } from '../types-v2';
import { formatNumber, formatPercent } from '../utils-v2';
import { TrendingUp, Zap, Check, Loader2, Sparkles } from 'lucide-react';
import { alphaAgentService } from '../services/alphaAgentService';
import { explainFactor } from '../services-v2/api';

interface FactorListProps {
  metrics: RealtimeMetrics | null;
}

export const FactorList: React.FC<FactorListProps> = ({ metrics }) => {
  const [promoting, setPromoting] = useState<Record<string, 'loading' | 'done' | 'error'>>({});
  const [explanations, setExplanations] = useState<Record<string, { loading: boolean; text?: string; error?: string }>>({});

  const handleExplain = async (factorId: string, factorName: string) => {
    // Check localStorage cache first
    const cacheKey = `alpha_explain_${factorId}`;
    const cached = localStorage.getItem(cacheKey);
    if (cached) {
      setExplanations(prev => ({ ...prev, [factorId]: { loading: false, text: cached } }));
      return;
    }

    setExplanations(prev => ({ ...prev, [factorId]: { loading: true } }));
    try {
      const result = await explainFactor(factorId);
      if (result.success && result.data?.explanation) {
        const text = result.data.explanation;
        localStorage.setItem(cacheKey, text);
        setExplanations(prev => ({ ...prev, [factorId]: { loading: false, text } }));
      } else {
        setExplanations(prev => ({ ...prev, [factorId]: { loading: false, error: '解释失败' } }));
      }
    } catch {
      setExplanations(prev => ({ ...prev, [factorId]: { loading: false, error: '请求失败' } }));
    }
  };

  const handlePromote = async (factorName: string, expression: string) => {
    setPromoting(prev => ({ ...prev, [factorName]: 'loading' }));
    try {
      const result = await alphaAgentService.promoteByExpression([{ name: factorName, expression }]);
      if (result.success && result.promoted.length > 0) {
        setPromoting(prev => ({ ...prev, [factorName]: 'done' }));
      } else {
        setPromoting(prev => ({ ...prev, [factorName]: 'error' }));
      }
    } catch {
      setPromoting(prev => ({ ...prev, [factorName]: 'error' }));
    }
  };

  const truncate = (str: string, max: number) => {
    if (!str) return '';
    return str.length > max ? str.substring(0, max) + '...' : str;
  };

  const formatMetric = (value: number | undefined | null, type: 'number' | 'percent' = 'number') => {
    if (value === undefined || value === null || value === 0) return <span className="text-muted-foreground/50">N/A</span>;
    return type === 'percent' ? formatPercent(value) : formatNumber(value, 4);
  };

  return (
    <Card className="glass card-hover animate-fade-in-up w-full">
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          <div className="h-2 w-2 rounded-full bg-purple-500 animate-pulse" />
          当前因子库 RankIC Top 10
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border/50">
                <th className="py-3 px-4 text-left font-medium text-muted-foreground w-1/6">因子名</th>
                <th className="py-3 px-4 text-left font-medium text-muted-foreground w-1/4">公式</th>
                <th className="py-3 px-4 text-right font-medium text-muted-foreground">IC</th>
                <th className="py-3 px-4 text-right font-medium text-muted-foreground">RankIC</th>
                <th className="py-3 px-4 text-right font-medium text-muted-foreground">ICIR</th>
                <th className="py-3 px-4 text-right font-medium text-muted-foreground">RankICIR</th>
                <th className="py-3 px-4 text-right font-medium text-muted-foreground">ARR</th>
                <th className="py-3 px-4 text-right font-medium text-muted-foreground">MDD</th>
                <th className="py-3 px-4 text-right font-medium text-muted-foreground">Sharpe</th>
                <th className="py-3 px-4 text-center font-medium text-muted-foreground">操作</th>
              </tr>
            </thead>
            <tbody>
              {metrics?.top10Factors && metrics.top10Factors.length > 0 ? (
                metrics.top10Factors.map((factor, index) => (
                  <HoverCard key={index} openDelay={200}>
                    <HoverCardTrigger asChild>
                      <tr className="group hover:bg-muted/50 transition-colors border-b border-border/50 last:border-0 cursor-help">
                        <td className="py-3 px-4 font-medium max-w-[150px] truncate" title={factor.factorName}>
                          {truncate(factor.factorName, 15)}
                        </td>
                        <td className="py-3 px-4 font-mono text-xs text-muted-foreground max-w-[200px] truncate">
                          {truncate(factor.factorExpression, 30)}
                        </td>
                        <td className="py-3 px-4 text-right font-mono">{formatMetric(factor.ic)}</td>
                        <td className="py-3 px-4 text-right font-mono font-bold text-primary">{formatMetric(factor.rankIc)}</td>
                        <td className="py-3 px-4 text-right font-mono">{formatMetric(factor.icir)}</td>
                        <td className="py-3 px-4 text-right font-mono">{formatMetric(factor.rankIcir)}</td>
                        <td className="py-3 px-4 text-right font-mono text-success">{formatMetric(factor.annualReturn, 'percent')}</td>
                        <td className="py-3 px-4 text-right font-mono text-destructive">{formatMetric(factor.maxDrawdown, 'percent')}</td>
                        <td className="py-3 px-4 text-right font-mono">{formatMetric(factor.sharpeRatio)}</td>
                        <td className="py-3 px-4 text-center">
                          {promoting[factor.factorName] === 'done' ? (
                            <span className="inline-flex items-center gap-1 text-xs text-green-500">
                              <Check size={12} /> 已加入
                            </span>
                          ) : promoting[factor.factorName] === 'loading' ? (
                            <Loader2 size={14} className="animate-spin mx-auto text-muted-foreground" />
                          ) : promoting[factor.factorName] === 'error' ? (
                            <span className="text-xs text-red-400">失败</span>
                          ) : (
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                handlePromote(factor.factorName, factor.factorExpression);
                              }}
                              className="inline-flex items-center gap-1 px-2 py-1 text-xs rounded-md
                                         bg-primary/10 text-primary hover:bg-primary/20
                                         border border-primary/20 transition-colors"
                              title="将此因子加入训练特征集"
                            >
                              <Zap size={12} /> 加入训练
                            </button>
                          )}
                        </td>
                      </tr>
                    </HoverCardTrigger>
                    <HoverCardContent 
                      className="w-[400px] glass-strong p-4 shadow-xl border border-primary/20" 
                      side="top" 
                      align="center"
                      sideOffset={10}
                      collisionPadding={20}
                      avoidCollisions={true}
                      style={{ zIndex: 1000 }}
                    >
                      <div className="space-y-4">
                        <div>
                          <div className="flex items-center justify-between mb-2">
                            <h4 className="font-bold text-primary text-base">{factor.factorName}</h4>
                            <div className="px-2 py-0.5 rounded-full bg-primary/10 text-primary text-xs font-medium border border-primary/20">
                               Score: {formatNumber(factor.rankIc * 100, 1)}
                            </div>
                          </div>
                          <div className="p-3 bg-secondary/40 rounded-lg font-mono text-xs break-all border border-border/50 text-foreground/90 shadow-inner">
                            {factor.factorExpression}
                          </div>
                        </div>
                        
                        <div className="grid grid-cols-2 gap-3 p-3 bg-background/40 rounded-lg border border-border/30">
                          <div>
                            <span className="text-xs text-muted-foreground block mb-0.5">年化收益 (ARR)</span>
                            <span className="font-bold text-success text-sm">{formatPercent(factor.annualReturn || 0)}</span>
                          </div>
                          <div>
                            <span className="text-xs text-muted-foreground block mb-0.5">夏普比率 (Sharpe)</span>
                            <span className="font-bold text-sm">{formatNumber(factor.sharpeRatio || 0, 2)}</span>
                          </div>
                          <div>
                            <span className="text-xs text-muted-foreground block mb-0.5">最大回撤 (MDD)</span>
                            <span className="font-bold text-destructive text-sm">{formatPercent(factor.maxDrawdown || 0)}</span>
                          </div>
                          <div>
                            <span className="text-xs text-muted-foreground block mb-0.5">卡玛比率 (CR)</span>
                            <span className="font-bold text-primary text-sm">{formatNumber(factor.calmarRatio || 0, 2)}</span>
                          </div>
                        </div>

                        {/* AI Explanation */}
                        {explanations[factor.factorId]?.text ? (
                          <div className="p-3 bg-primary/5 rounded-lg border border-primary/20">
                            <div className="flex items-center gap-1.5 mb-2">
                              <Sparkles className="h-3.5 w-3.5 text-primary" />
                              <span className="text-xs font-medium text-primary">AI 解读</span>
                            </div>
                            <div className="text-xs text-foreground/80 whitespace-pre-line leading-relaxed">
                              {explanations[factor.factorId].text}
                            </div>
                          </div>
                        ) : (
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleExplain(factor.factorId, factor.factorName);
                            }}
                            disabled={explanations[factor.factorId]?.loading}
                            className="w-full flex items-center justify-center gap-1.5 px-3 py-2 text-xs rounded-lg
                                       bg-primary/10 text-primary hover:bg-primary/20 disabled:opacity-50
                                       border border-primary/20 transition-colors"
                          >
                            {explanations[factor.factorId]?.loading ? (
                              <><Loader2 size={12} className="animate-spin" /> AI 解读中...</>
                            ) : explanations[factor.factorId]?.error ? (
                              <span className="text-destructive">{explanations[factor.factorId].error}</span>
                            ) : (
                              <><Sparkles size={12} /> AI 解读因子</>
                            )}
                          </button>
                        )}

                      </div>
                    </HoverCardContent>
                  </HoverCard>
                ))
              ) : (
                <tr>
                  <td colSpan={10} className="py-8 text-center text-muted-foreground">
                    暂无因子数据
                  </td>
                </tr>
              )}

            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
};

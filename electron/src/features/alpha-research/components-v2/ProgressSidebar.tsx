import React from 'react';
import { Card, CardContent } from './ui/Card';
import { Badge } from './ui/Badge';
import { ExecutionProgress, TimelineLoop, TimelinePhase, TokenUsage } from '../types-v2';
import {
  Sparkles, Brain, Code2, TrendingUp, CheckCircle2, Clock,
  Zap, Loader2, BarChart3,
} from 'lucide-react';

interface ProgressSidebarProps {
  progress: ExecutionProgress;
  timeline?: TimelineLoop[];
  tokenUsage?: TokenUsage;
}

const phaseConfig: Record<string, { icon: typeof Sparkles; color: string; bg: string }> = {
  hypothesis: { icon: Brain, color: 'text-purple-400', bg: 'bg-purple-500/10' },
  experiment: { icon: Sparkles, color: 'text-blue-400', bg: 'bg-blue-500/10' },
  coder:      { icon: Code2, color: 'text-amber-400', bg: 'bg-amber-500/10' },
  runner:     { icon: BarChart3, color: 'text-green-400', bg: 'bg-green-500/10' },
  feedback:   { icon: TrendingUp, color: 'text-cyan-400', bg: 'bg-cyan-500/10' },
};

const statusIcon = (status: string) => {
  if (status === 'completed') return <CheckCircle2 className="h-3.5 w-3.5 text-green-400" />;
  if (status === 'running') return <Loader2 className="h-3.5 w-3.5 text-blue-400 animate-spin" />;
  return <Clock className="h-3.5 w-3.5 text-muted-foreground/40" />;
};

const formatDuration = (s: number | null) => {
  if (s == null) return '--';
  if (s < 60) return `${s.toFixed(0)}s`;
  return `${Math.floor(s / 60)}m${(s % 60).toFixed(0)}s`;
};

const formatTokens = (n: number) => {
  if (n < 1000) return String(n);
  if (n < 1000000) return `${(n / 1000).toFixed(1)}k`;
  return `${(n / 1000000).toFixed(1)}M`;
};

export const ProgressSidebar: React.FC<ProgressSidebarProps> = ({
  progress, timeline, tokenUsage,
}) => {
  const totalPhases = (progress.totalRounds || 1) * 5;
  const completedPhases = timeline
    ? timeline.reduce((sum, l) => sum + l.phases.filter(p => p.status === 'completed').length, 0)
    : 0;

  return (
    <div className="space-y-3">
      {/* Summary Card */}
      <Card className="glass card-hover animate-fade-in-left">
        <CardContent className="p-3">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <div className="p-2 rounded-lg bg-primary/10">
                <Zap className="h-4 w-4 text-primary animate-pulse" />
              </div>
              <div>
                <div className="text-sm font-bold">{progress.message || '准备中...'}</div>
                <div className="text-[10px] text-muted-foreground">
                  Round {progress.currentRound + 1}/{progress.totalRounds}
                </div>
              </div>
            </div>
            <Badge variant="default" className="text-xs font-mono">
              {progress.progress.toFixed(0)}%
            </Badge>
          </div>
          <div className="relative h-1.5 rounded-full overflow-hidden bg-secondary/30">
            <div
              className="absolute left-0 top-0 h-full bg-gradient-to-r from-blue-500 to-purple-500 transition-all duration-500"
              style={{ width: `${progress.progress}%` }}
            />
          </div>

          {/* Token usage summary */}
          {tokenUsage && tokenUsage.total_calls > 0 && (
            <div className="flex items-center gap-3 mt-2 text-[10px] text-muted-foreground">
              <span>LLM: {tokenUsage.total_calls} 次</span>
              <span>输入: {formatTokens(tokenUsage.total_prompt_tokens)}</span>
              <span>输出: {formatTokens(tokenUsage.total_completion_tokens)}</span>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Timeline Card */}
      <Card className="glass card-hover animate-fade-in-left" style={{ animationDelay: '0.1s' }}>
        <CardContent className="p-3">
          <div className="text-xs font-medium mb-3 text-muted-foreground">
            执行时间线
            {timeline && (
              <span className="ml-2 text-[10px]">({completedPhases}/{totalPhases} 步完成)</span>
            )}
          </div>

          <div className="space-y-2 max-h-[420px] overflow-y-auto pr-1">
            {!timeline || timeline.length === 0 ? (
              <div className="flex items-center gap-2 text-xs text-muted-foreground py-4 justify-center">
                <Loader2 className="h-3 w-3 animate-spin" />
                等待启动...
              </div>
            ) : (
              timeline.map((loop) => (
                <LoopCard key={loop.loop} loop={loop} />
              ))
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

const LoopCard: React.FC<{ loop: TimelineLoop }> = ({ loop }) => {
  const isCompleted = loop.status === 'completed';
  const isRunning = loop.status === 'running';

  return (
    <div className={`rounded-lg border p-2 transition-all ${
      isRunning ? 'border-blue-500/30 bg-blue-500/5' :
      isCompleted ? 'border-green-500/20 bg-green-500/5' :
      'border-border/50'
    }`}>
      {/* Loop header */}
      <div className="flex items-center justify-between mb-1.5">
        <div className="flex items-center gap-1.5">
          {isCompleted ? (
            <CheckCircle2 className="h-3.5 w-3.5 text-green-400" />
          ) : isRunning ? (
            <Loader2 className="h-3.5 w-3.5 text-blue-400 animate-spin" />
          ) : (
            <Clock className="h-3.5 w-3.5 text-muted-foreground/40" />
          )}
          <span className={`text-xs font-bold ${isRunning ? 'text-blue-400' : isCompleted ? 'text-green-400' : 'text-muted-foreground'}`}>
            {loop.label}
          </span>
        </div>
        <Badge variant={isCompleted ? 'success' : isRunning ? 'default' : 'default'} className="text-[9px] px-1 py-0">
          {isCompleted ? '完成' : isRunning ? '运行中' : '等待'}
        </Badge>
      </div>

      {/* Phases */}
      <div className="space-y-1">
        {loop.phases.map((phase, idx) => (
          <PhaseRow key={`${phase.key}-${idx}`} phase={phase} />
        ))}
        {loop.phases.length === 0 && isRunning && (
          <div className="flex items-center gap-2 text-[10px] text-muted-foreground py-1">
            <Loader2 className="h-3 w-3 animate-spin" />
            初始化中...
          </div>
        )}
      </div>
    </div>
  );
};

const PhaseRow: React.FC<{ phase: TimelinePhase }> = ({ phase }) => {
  const config = phaseConfig[phase.key] || phaseConfig.hypothesis;
  const Icon = config.icon;
  const isRunning = phase.status === 'running';
  const isCompleted = phase.status === 'completed';

  return (
    <div className={`flex items-center gap-2 rounded px-1.5 py-1 transition-all ${
      isRunning ? `${config.bg}` : ''
    }`}>
      <Icon className={`h-3 w-3 flex-shrink-0 ${
        isRunning ? `${config.color} animate-pulse` :
        isCompleted ? config.color :
        'text-muted-foreground/30'
      }`} />
      <span className={`text-[10px] flex-1 ${
        isRunning ? 'font-semibold text-foreground' :
        isCompleted ? 'text-foreground/80' :
        'text-muted-foreground/50'
      }`}>
        {phase.label}
      </span>

      {/* Duration */}
      {phase.duration_s != null && (
        <span className="text-[9px] text-muted-foreground font-mono tabular-nums">
          {formatDuration(phase.duration_s)}
        </span>
      )}

      {/* Tokens */}
      {phase.tokens && phase.tokens.calls > 0 && (
        <span className="text-[9px] text-muted-foreground/60">
          {formatTokens(phase.tokens.prompt + phase.tokens.completion)}t
        </span>
      )}

      {/* Factor names */}
      {phase.factors && phase.factors.length > 0 && (
        <span className="text-[9px] text-blue-400/70 max-w-[80px] truncate" title={phase.factors.join(', ')}>
          {phase.factors.length}因子
        </span>
      )}

      {statusIcon(phase.status)}
    </div>
  );
};

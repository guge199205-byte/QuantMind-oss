import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/Card';
import { RealtimeMetrics } from '../types-v2';
import { formatNumber, formatPercent } from '../utils-v2';
import { TrendingUp, TrendingDown } from 'lucide-react';

interface MetricsPanelProps {
  metrics: RealtimeMetrics | null;
}

interface MetricCardProps {
  label: string;
  value: string;
  trend?: number;
  description?: string;
}

const MetricCard: React.FC<MetricCardProps> = ({ label, value, trend, description }) => {
  const isPositive = trend !== undefined && trend > 0;
  const isNegative = trend !== undefined && trend < 0;

  return (
    <div className="rounded-lg border border-border bg-secondary/30 p-4">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <p className="text-xs text-muted-foreground">{label}</p>
          <p className="mt-1 text-2xl font-bold">{value}</p>
          {description && (
            <p className="mt-1 text-xs text-muted-foreground">{description}</p>
          )}
        </div>
        {trend !== undefined && (
          <div
            className={`flex items-center gap-1 text-xs font-medium ${
              isPositive ? 'text-success' : isNegative ? 'text-destructive' : 'text-muted-foreground'
            }`}
          >
            {isPositive ? (
              <TrendingUp className="h-3 w-3" />
            ) : isNegative ? (
              <TrendingDown className="h-3 w-3" />
            ) : null}
            {trend > 0 ? '+' : ''}
            {formatPercent(trend, 1)}
          </div>
        )}
      </div>
    </div>
  );
};

export const MetricsPanel: React.FC<MetricsPanelProps> = ({ metrics }) => {
  if (!metrics) {
    return (
      <Card className="h-full">
        <CardHeader className="pb-3">
          <CardTitle className="text-base">📈 实时回测结果</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex h-[400px] items-center justify-center text-muted-foreground">
            等待回测数据...
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="h-full">
      <CardHeader className="pb-3">
        <CardTitle className="text-base">📈 实时回测结果</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* IC Metrics */}
        <div>
          <h4 className="mb-2 text-sm font-medium text-muted-foreground">IC 指标</h4>
          <div className="grid grid-cols-2 gap-3">
            <MetricCard
              label="IC"
              value={formatNumber(metrics.ic, 4)}
              description="信息系数"
            />
            <MetricCard
              label="ICIR"
              value={formatNumber(metrics.icir, 3)}
              description="IC信息比率"
            />
            <MetricCard
              label="RankIC"
              value={formatNumber(metrics.rankIc, 4)}
              description="秩相关系数"
            />
            <MetricCard
              label="RankICIR"
              value={formatNumber(metrics.rankIcir, 3)}
              description="RankIC信息比率"
            />
          </div>
        </div>

        {/* Return Metrics */}
        <div>
          <h4 className="mb-2 text-sm font-medium text-muted-foreground">收益指标</h4>
          <div className="grid grid-cols-2 gap-3">
            <MetricCard
              label="年化收益"
              value={formatPercent(metrics.annualReturn)}
              trend={metrics.annualReturn}
            />
            <MetricCard
              label="夏普比率"
              value={formatNumber(metrics.sharpeRatio, 2)}
            />
            <MetricCard
              label="最大回撤"
              value={formatPercent(metrics.maxDrawdown)}
              trend={metrics.maxDrawdown}
            />
          </div>
        </div>

        {/* Factor Statistics */}
        <div>
          <h4 className="mb-2 text-sm font-medium text-muted-foreground">因子统计</h4>
          <div className="rounded-lg border border-border bg-secondary/30 p-4">
            <div className="flex items-center justify-between">
              <div className="flex-1">
                <p className="text-xs text-muted-foreground">总因子数</p>
                <p className="mt-1 text-2xl font-bold">{metrics.totalFactors}</p>
              </div>
              <div className="flex gap-4 text-xs">
                <div className="text-center">
                  <div className="font-medium text-success">{metrics.highQualityFactors}</div>
                  <div className="text-muted-foreground">高质量</div>
                </div>
                <div className="text-center">
                  <div className="font-medium text-warning">{metrics.mediumQualityFactors}</div>
                  <div className="text-muted-foreground">中等</div>
                </div>
                <div className="text-center">
                  <div className="font-medium text-destructive">{metrics.lowQualityFactors}</div>
                  <div className="text-muted-foreground">低质量</div>
                </div>
              </div>
            </div>

            {/* Quality Distribution Bar */}
            <div className="mt-3 flex h-2 overflow-hidden rounded-full">
              <div
                className="bg-success"
                style={{
                  width: `${(metrics.highQualityFactors / metrics.totalFactors) * 100}%`,
                }}
              />
              <div
                className="bg-warning"
                style={{
                  width: `${(metrics.mediumQualityFactors / metrics.totalFactors) * 100}%`,
                }}
              />
              <div
                className="bg-destructive"
                style={{
                  width: `${(metrics.lowQualityFactors / metrics.totalFactors) * 100}%`,
                }}
              />
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

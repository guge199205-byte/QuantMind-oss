import type React from 'react';
import { useState } from 'react';
import { Bell, Trash2 } from 'lucide-react';
import { Badge, Button, Card, ConfirmDialog, EmptyState, Pagination, Select } from '../common';
import type { AlertRuleItem, AlertType } from '../../types/alerts';
import { formatDateTime } from '../../utils/format';

export type AlertRuleEnabledFilter = 'all' | 'enabled' | 'disabled';
export type AlertTypeFilter = 'all' | AlertType;
export type AlertRuleBusyAction = 'test' | 'toggle' | 'delete';

export interface AlertRuleBusyState {
  id: number;
  action: AlertRuleBusyAction;
}

const ENABLED_FILTER_OPTIONS = [
  { value: 'all', label: '全部状态' },
  { value: 'enabled', label: '已启用' },
  { value: 'disabled', label: '已停用' },
];

const ALERT_TYPE_FILTER_OPTIONS = [
  { value: 'all', label: '全部类型' },
  { value: 'price_cross', label: '价格突破' },
  { value: 'price_change_percent', label: '涨跌幅' },
  { value: 'volume_spike', label: '成交量放大' },
  { value: 'ma_price_cross', label: '价格均线穿越' },
  { value: 'rsi_threshold', label: 'RSI 阈值' },
  { value: 'macd_cross', label: 'MACD 金叉/死叉' },
  { value: 'kdj_cross', label: 'KDJ 金叉/死叉' },
  { value: 'cci_threshold', label: 'CCI 阈值' },
  { value: 'portfolio_stop_loss', label: '组合止损' },
  { value: 'portfolio_concentration', label: '组合集中度' },
  { value: 'portfolio_drawdown', label: '组合回撤' },
  { value: 'portfolio_price_stale', label: '组合价格状态' },
  { value: 'market_light_status', label: '大盘红绿灯状态' },
  { value: 'market_light_score_drop', label: '大盘红绿灯分数下降' },
];

const typeLabel: Record<AlertType, string> = {
  price_cross: '价格突破',
  price_change_percent: '涨跌幅',
  volume_spike: '成交量放大',
  ma_price_cross: '价格均线穿越',
  rsi_threshold: 'RSI 阈值',
  macd_cross: 'MACD 金叉/死叉',
  kdj_cross: 'KDJ 金叉/死叉',
  cci_threshold: 'CCI 阈值',
  portfolio_stop_loss: '组合止损',
  portfolio_concentration: '组合集中度',
  portfolio_drawdown: '组合回撤',
  portfolio_price_stale: '组合价格状态',
  market_light_status: '大盘红绿灯状态',
  market_light_score_drop: '大盘红绿灯分数下降',
};

const severityLabel: Record<string, string> = {
  info: '提示',
  warning: '警告',
  critical: '严重',
};

const scopeLabel: Record<string, string> = {
  single_symbol: '单标的',
  watchlist: '自选股',
  portfolio_holdings: '持仓标的',
  portfolio_account: '持仓账户',
  market: '大盘市场',
};

const marketRegionLabel: Record<string, string> = {
  cn: 'A 股',
  hk: '港股',
  us: '美股',
};

const marketLightStatusLabel: Record<string, string> = {
  yellow: '黄灯',
  red: '红灯',
};

function formatParameters(rule: AlertRuleItem): string {
  if (rule.alertType === 'market_light_status') {
    const statuses = rule.parameters.statuses ?? [];
    return statuses.length > 0
      ? statuses.map((status) => marketLightStatusLabel[status] ?? status).join(' / ')
      : '--';
  }
  if (rule.alertType === 'market_light_score_drop') {
    return `Score 下降 >= ${rule.parameters.minDrop ?? '--'}`;
  }
  if (rule.alertType === 'price_cross') {
    return `${rule.parameters.direction === 'below' ? '下破' : '上破'} ${rule.parameters.price ?? '--'}`;
  }
  if (rule.alertType === 'price_change_percent') {
    return `${rule.parameters.direction === 'down' ? '下跌' : '上涨'} ${rule.parameters.changePct ?? '--'}%`;
  }
  if (rule.alertType === 'volume_spike') {
    return `${rule.parameters.multiplier ?? '--'}x`;
  }
  if (rule.alertType === 'ma_price_cross') {
    return `${rule.parameters.direction === 'below' ? '下穿' : '上穿'} MA${rule.parameters.window ?? '--'}`;
  }
  if (rule.alertType === 'rsi_threshold') {
    return `RSI${rule.parameters.period ?? '--'} ${rule.parameters.direction === 'below' ? '下穿' : '上穿'} ${rule.parameters.threshold ?? '--'}`;
  }
  if (rule.alertType === 'macd_cross' || rule.alertType === 'kdj_cross') {
    const direction = rule.parameters.direction === 'bearish_cross' ? '死叉' : '金叉';
    if (rule.alertType === 'macd_cross') {
      return `MACD(${rule.parameters.fastPeriod ?? '--'},${rule.parameters.slowPeriod ?? '--'},${rule.parameters.signalPeriod ?? '--'}) ${direction}`;
    }
    return `KDJ(${rule.parameters.period ?? '--'},${rule.parameters.kPeriod ?? '--'},${rule.parameters.dPeriod ?? '--'}) ${direction}`;
  }
  if (rule.alertType === 'portfolio_stop_loss') {
    return rule.parameters.mode === 'breach' ? '已触发止损' : '接近止损';
  }
  if (rule.alertType === 'portfolio_concentration') return 'top_weight_pct';
  if (rule.alertType === 'portfolio_drawdown') return 'max_drawdown_pct';
  if (rule.alertType === 'portfolio_price_stale') return 'price_stale / price_available';
  return `CCI${rule.parameters.period ?? '--'} ${rule.parameters.direction === 'below' ? '下穿' : '上穿'} ${rule.parameters.threshold ?? '--'}`;
}

function isCoolingDown(rule: AlertRuleItem): boolean {
  return rule.cooldownActive === true;
}

function formatTarget(rule: AlertRuleItem): string {
  if (rule.targetScope === 'market') return marketRegionLabel[rule.target] ?? rule.target;
  if (rule.targetScope === 'watchlist') return 'default';
  if (rule.targetScope === 'portfolio_account' || rule.targetScope === 'portfolio_holdings') {
    return rule.target === 'all' ? '全部账户' : `账户 ${rule.target}`;
  }
  return rule.target;
}

function hasChildTargetCooldown(rule: AlertRuleItem): boolean {
  return rule.targetScope === 'watchlist' || rule.targetScope === 'portfolio_holdings';
}

interface AlertRuleListProps {
  rules: AlertRuleItem[];
  total: number;
  page: number;
  pageSize: number;
  className?: string;
  isLoading?: boolean;
  enabledFilter: AlertRuleEnabledFilter;
  alertTypeFilter: AlertTypeFilter;
  onEnabledFilterChange: (value: AlertRuleEnabledFilter) => void;
  onAlertTypeFilterChange: (value: AlertTypeFilter) => void;
  onPageChange: (page: number) => void;
  onToggleEnabled: (rule: AlertRuleItem) => void;
  onDelete: (rule: AlertRuleItem) => void;
  onTest: (rule: AlertRuleItem) => void;
  busyRule?: AlertRuleBusyState | null;
}

export const AlertRuleList: React.FC<AlertRuleListProps> = ({
  rules,
  total,
  page,
  pageSize,
  className,
  isLoading = false,
  enabledFilter,
  alertTypeFilter,
  onEnabledFilterChange,
  onAlertTypeFilterChange,
  onPageChange,
  onToggleEnabled,
  onDelete,
  onTest,
  busyRule = null,
}) => {
  const [pendingDelete, setPendingDelete] = useState<AlertRuleItem | null>(null);
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const isRuleBusy = (rule: AlertRuleItem) => busyRule?.id === rule.id;
  const isRuleActionBusy = (rule: AlertRuleItem, action: AlertRuleBusyAction) => (
    busyRule?.id === rule.id && busyRule.action === action
  );

  return (
    <Card title="告警规则" subtitle={`${total} 条规则`} variant="bordered" padding="md" className={className}>
      <div className="mb-4 grid gap-3 md:grid-cols-2">
        <Select
          label="启停状态"
          value={enabledFilter}
          options={ENABLED_FILTER_OPTIONS}
          onChange={(value) => {
            onEnabledFilterChange(value as AlertRuleEnabledFilter);
          }}
        />
        <Select
          label="规则类型"
          value={alertTypeFilter}
          options={ALERT_TYPE_FILTER_OPTIONS}
          onChange={(value) => {
            onAlertTypeFilterChange(value as AlertTypeFilter);
          }}
        />
      </div>

      {rules.length === 0 ? (
        <div className="flex min-h-[220px] flex-1 items-center justify-center">
          <EmptyState
            icon={<Bell className="h-6 w-6" />}
            title={isLoading ? '正在加载规则' : '暂无告警规则'}
            description="创建规则后，后台评估任务会按轮询周期处理已启用的告警。"
          />
        </div>
      ) : (
        <div className="min-h-0 flex-1 overflow-x-auto">
          <table className="w-full min-w-[960px] text-left text-sm">
            <thead className="border-b border-border/60 text-xs uppercase text-muted-text">
              <tr>
                <th className="px-3 py-2 font-medium">规则</th>
                <th className="px-3 py-2 font-medium">目标</th>
                <th className="px-3 py-2 font-medium">类型</th>
                <th className="px-3 py-2 font-medium">参数</th>
                <th className="px-3 py-2 font-medium">状态</th>
                <th className="px-3 py-2 font-medium">冷却</th>
                <th className="px-3 py-2 font-medium">更新时间</th>
                <th className="px-3 py-2 text-right font-medium">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/40">
              {rules.map((rule) => (
                <tr key={rule.id} className="align-top">
                  <td className="px-3 py-3">
                    <div className="font-medium text-foreground">{rule.name}</div>
                    <div className="mt-1 text-xs text-muted-text">来源：{rule.source}</div>
                  </td>
                  <td className="px-3 py-3 text-secondary-text">
                    <div className="font-mono">{formatTarget(rule)}</div>
                    <div className="mt-1 text-xs">{scopeLabel[rule.targetScope] ?? rule.targetScope}</div>
                  </td>
                  <td className="px-3 py-3">
                    <div className="flex flex-col items-start gap-1">
                      <Badge variant="info">{typeLabel[rule.alertType]}</Badge>
                      <Badge variant={rule.severity === 'critical' ? 'danger' : rule.severity === 'warning' ? 'warning' : 'default'}>
                        {severityLabel[rule.severity] ?? rule.severity}
                      </Badge>
                    </div>
                  </td>
                  <td className="px-3 py-3 text-secondary-text">{formatParameters(rule)}</td>
                  <td className="px-3 py-3">
                    <Badge variant={rule.enabled ? 'success' : 'default'}>
                      {rule.enabled ? '已启用' : '已停用'}
                    </Badge>
                  </td>
                  <td className="px-3 py-3 text-xs text-secondary-text">
                    <div>{isCoolingDown(rule) ? '冷却中' : '未冷却'}</div>
                    <div className="mt-1">{formatDateTime(rule.cooldownUntil)}</div>
                    {hasChildTargetCooldown(rule) ? (
                      <div className="mt-1 text-muted-text">子目标见触发历史</div>
                    ) : null}
                  </td>
                  <td className="px-3 py-3 text-xs text-secondary-text">{formatDateTime(rule.updatedAt ?? rule.createdAt)}</td>
                  <td className="px-3 py-3">
                    <div className="flex justify-end gap-2">
                      <Button
                        size="xsm"
                        variant="outline"
                        onClick={() => onTest(rule)}
                        isLoading={isRuleActionBusy(rule, 'test')}
                        loadingText="测试中"
                        disabled={isRuleBusy(rule) && !isRuleActionBusy(rule, 'test')}
                      >
                        测试
                      </Button>
                      <Button
                        size="xsm"
                        variant={rule.enabled ? 'secondary' : 'primary'}
                        onClick={() => onToggleEnabled(rule)}
                        isLoading={isRuleActionBusy(rule, 'toggle')}
                        loadingText={rule.enabled ? '停用中' : '启用中'}
                        disabled={isRuleBusy(rule) && !isRuleActionBusy(rule, 'toggle')}
                      >
                        {rule.enabled ? '停用' : '启用'}
                      </Button>
                      <Button
                        size="xsm"
                        variant="danger-subtle"
                        aria-label={`删除 ${rule.name}`}
                        onClick={() => setPendingDelete(rule)}
                        disabled={isRuleBusy(rule)}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                        删除
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Pagination
        currentPage={page}
        totalPages={totalPages}
        onPageChange={onPageChange}
        className="mt-5"
      />

      <ConfirmDialog
        isOpen={pendingDelete != null}
        title="删除告警规则"
        message={pendingDelete ? `确认删除「${pendingDelete.name}」吗？该操作不会删除已有触发历史。` : ''}
        confirmText="删除"
        cancelText="取消"
        isDanger
        onConfirm={() => {
          if (pendingDelete) {
            onDelete(pendingDelete);
          }
          setPendingDelete(null);
        }}
        onCancel={() => setPendingDelete(null)}
      />
    </Card>
  );
};

import React from 'react';
import type { ExecutionConfig, LiveTradeConfig, TradeWeekday, TradingSession } from '../../../types/liveTrading';
import type { ValidationIssue } from '../utils/liveTradeConfigValidation';

type Props = {
  executionConfig: ExecutionConfig;
  liveTradeConfig: LiveTradeConfig;
  onExecutionConfigChange: (val: ExecutionConfig) => void;
  onLiveTradeConfigChange: (val: LiveTradeConfig) => void;
  validationIssues?: ValidationIssue[];
};

const WEEKDAYS: TradeWeekday[] = ['MON', 'TUE', 'WED', 'THU', 'FRI'];
const SESSIONS: TradingSession[] = ['AM', 'PM'];

const SESSION_RANGES: Record<TradingSession, [string, string]> = {
  AM: ['09:00', '11:30'],
  PM: ['13:00', '15:00'],
};

const SESSION_DEFAULTS: Record<string, { sell_time: string; buy_time: string }> = {
  AM: { sell_time: '09:00', buy_time: '09:05' },
  PM: { sell_time: '14:30', buy_time: '14:45' },
  'AM,PM': { sell_time: '09:00', buy_time: '09:05' },
};

function isTimeInSessions(time: string, sessions: TradingSession[]): boolean {
  return sessions.some((s) => {
    const [start, end] = SESSION_RANGES[s];
    return time >= start && time <= end;
  });
}

const fieldError = (issues: ValidationIssue[] | undefined, field: string) =>
  issues?.find((item) => item.field === field)?.message;

const controlClassName =
  'w-full rounded-2xl border border-gray-300 bg-white px-4 py-2.5 text-sm text-gray-900 outline-none transition-colors focus:border-blue-500';

const LiveTradeConfigForm: React.FC<Props> = ({
  executionConfig,
  liveTradeConfig,
  onExecutionConfigChange,
  onLiveTradeConfigChange,
  validationIssues,
}) => {
  const updateLive = (patch: Partial<LiveTradeConfig>) => {
    onLiveTradeConfigChange({ ...liveTradeConfig, ...patch });
  };

  const updateExec = (patch: Partial<ExecutionConfig>) => {
    onExecutionConfigChange({ ...executionConfig, ...patch });
  };

  const handleScheduleTypeChange = (value: LiveTradeConfig['schedule_type']) => {
    if (value === 'weekly') {
      const currentDays = liveTradeConfig.trade_weekdays || [];
      updateLive({
        schedule_type: value,
        trade_weekdays: currentDays.length > 0 ? currentDays : ['MON'],
      });
      return;
    }
    updateLive({ schedule_type: value });
  };

  return (
    <div className="space-y-3">
      <section className="rounded-2xl border border-gray-200 p-3.5 md:p-4">
        <div className="mb-2.5 font-semibold text-gray-900">调仓节奏</div>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <label>
            <div className="mb-1 text-sm">调度方式</div>
            <select
              className={controlClassName}
              value={liveTradeConfig.schedule_type}
              onChange={(e) => handleScheduleTypeChange(e.target.value as LiveTradeConfig['schedule_type'])}
            >
              <option value="interval">按交易日间隔</option>
              <option value="weekly">按周执行</option>
            </select>
          </label>

          {liveTradeConfig.schedule_type === 'interval' ? (
            <label>
              <div className="mb-1 text-sm">调仓周期</div>
              <select
                className={controlClassName}
                value={liveTradeConfig.rebalance_days || 3}
                onChange={(e) => updateLive({ rebalance_days: Number(e.target.value) as 1 | 3 | 5 | 10 | 20 })}
              >
                {[1, 3, 5, 10, 20].map((v) => (
                  <option key={v} value={v}>
                    每 {v} 个交易日
                  </option>
                ))}
              </select>
              {fieldError(validationIssues, 'rebalance_days') && (
                <div className="text-xs text-red-500 mt-1">{fieldError(validationIssues, 'rebalance_days')}</div>
              )}
            </label>
          ) : (
            <div>
              <div className="mb-1 text-sm">每周调仓日（可多选）</div>
              <div className="flex flex-wrap gap-2">
                {WEEKDAYS.map((day) => {
                  const selected = !!liveTradeConfig.trade_weekdays?.includes(day);
                  return (
                    <button
                      type="button"
                      key={day}
                      className={`rounded-2xl border px-3.5 py-2 text-sm transition-colors ${
                        selected ? 'border-blue-600 bg-blue-600 text-white' : 'border-gray-300 bg-white text-gray-700'
                      }`}
                      onClick={() => {
                        const current = liveTradeConfig.trade_weekdays || [];
                        updateLive({
                          trade_weekdays: selected ? current.filter((item) => item !== day) : [...current, day],
                        });
                      }}
                    >
                      {day}
                    </button>
                  );
                })}
              </div>
              {fieldError(validationIssues, 'trade_weekdays') && (
                <div className="text-xs text-red-500 mt-1">{fieldError(validationIssues, 'trade_weekdays')}</div>
              )}
            </div>
          )}
        </div>

        <div className="mt-3">
          <div className="mb-1 text-sm">执行时段</div>
          <div className="flex gap-2">
            {SESSIONS.map((session) => {
              const selected = liveTradeConfig.enabled_sessions.includes(session);
              return (
                <button
                  type="button"
                  key={session}
                  className={`rounded-2xl border px-4 py-2 text-sm transition-colors ${
                    selected ? 'border-slate-900 bg-slate-900 text-white' : 'border-gray-300 bg-white text-gray-700'
                  }`}
                  onClick={() => {
                    const current = liveTradeConfig.enabled_sessions || [];
                    const next = (selected
                      ? current.filter((item) => item !== session)
                      : [...current, session]) as TradingSession[];

                    // Auto-adjust sell/buy times if they no longer fall in the new session set
                    const patch: Partial<LiveTradeConfig> = { enabled_sessions: next };
                    if (next.length > 0) {
                      const key = [...next].sort().join(',');
                      const defaults = SESSION_DEFAULTS[key] || SESSION_DEFAULTS['PM'];
                      if (!isTimeInSessions(liveTradeConfig.sell_time, next)) {
                        patch.sell_time = defaults.sell_time;
                      }
                      if (!isTimeInSessions(liveTradeConfig.buy_time, next)) {
                        patch.buy_time = defaults.buy_time;
                      }
                      // Ensure sell_time < buy_time after reset
                      const newSell = patch.sell_time ?? liveTradeConfig.sell_time;
                      const newBuy = patch.buy_time ?? liveTradeConfig.buy_time;
                      if (newSell >= newBuy) {
                        patch.buy_time = defaults.buy_time;
                        patch.sell_time = defaults.sell_time;
                      }
                    }
                    updateLive(patch);
                  }}
                >
                  {session === 'AM' ? '上午' : '下午'}
                </button>
              );
            })}
          </div>
          {fieldError(validationIssues, 'enabled_sessions') && (
            <div className="text-xs text-red-500 mt-1">{fieldError(validationIssues, 'enabled_sessions')}</div>
          )}
          {liveTradeConfig.enabled_sessions.length > 0 && (
            <div className="mt-1 text-xs text-gray-400">
              可用时间段：
              {liveTradeConfig.enabled_sessions
                .sort()
                .map((s) => `${s === 'AM' ? '上午' : '下午'} ${SESSION_RANGES[s][0]}–${SESSION_RANGES[s][1]}`)
                .join('，')}
            </div>
          )}
        </div>
      </section>

      <section className="rounded-2xl border border-gray-200 p-3.5 md:p-4">
        <div className="mb-2.5 font-semibold text-gray-900">买卖时点</div>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_200px]">
          <label>
            <div className="mb-1 text-sm">卖出时间</div>
            <input
              type="time"
              className={`${controlClassName} ${!isTimeInSessions(liveTradeConfig.sell_time, liveTradeConfig.enabled_sessions) ? 'border-red-500 bg-red-50' : ''}`}
              value={liveTradeConfig.sell_time}
              min={liveTradeConfig.enabled_sessions.includes('AM') ? '09:00' : '13:00'}
              max={liveTradeConfig.enabled_sessions.includes('PM') ? '15:00' : '11:30'}
              onChange={(e) => {
                const val = e.target.value;
                updateLive({ sell_time: val });
              }}
            />
            {!isTimeInSessions(liveTradeConfig.sell_time, liveTradeConfig.enabled_sessions) && (
              <div className="text-xs text-red-500 mt-1">卖出时间必须在所选执行时段内</div>
            )}
            {fieldError(validationIssues, 'sell_time') && (
              <div className="text-xs text-red-500 mt-1">{fieldError(validationIssues, 'sell_time')}</div>
            )}
          </label>

          <label>
            <div className="mb-1 text-sm">买入时间</div>
            <input
              type="time"
              className={`${controlClassName} ${!isTimeInSessions(liveTradeConfig.buy_time, liveTradeConfig.enabled_sessions) ? 'border-red-500 bg-red-50' : ''}`}
              value={liveTradeConfig.buy_time}
              min={liveTradeConfig.enabled_sessions.includes('AM') ? '09:00' : '13:00'}
              max={liveTradeConfig.enabled_sessions.includes('PM') ? '15:00' : '11:30'}
              onChange={(e) => {
                const val = e.target.value;
                updateLive({ buy_time: val });
              }}
            />
            {!isTimeInSessions(liveTradeConfig.buy_time, liveTradeConfig.enabled_sessions) && (
              <div className="text-xs text-red-500 mt-1">买入时间必须在所选执行时段内</div>
            )}
            {fieldError(validationIssues, 'buy_time') && (
              <div className="text-xs text-red-500 mt-1">{fieldError(validationIssues, 'buy_time')}</div>
            )}
          </label>

          <label className="mt-7 flex min-h-[44px] items-center gap-2 rounded-2xl border border-gray-200 px-4">
            <input
              type="checkbox"
              checked={liveTradeConfig.sell_first}
              onChange={(e) => updateLive({ sell_first: e.target.checked })}
            />
            <span className="text-sm">先卖后买</span>
          </label>
        </div>
      </section>

      <section className="rounded-2xl border border-gray-200 p-3.5 md:p-4">
        <div className="mb-2.5 font-semibold text-gray-900">委托执行</div>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          <label>
            <div className="mb-1 text-sm">委托方式</div>
            <select
              className={controlClassName}
              value={liveTradeConfig.order_type}
              onChange={(e) => updateLive({ order_type: e.target.value as LiveTradeConfig['order_type'] })}
            >
              <option value="LIMIT">限价</option>
              <option value="MARKET">市价</option>
            </select>
          </label>

          <label>
            <div className="mb-1 text-sm">价格偏离容忍</div>
            <div className="relative">
              <input
                type="number"
                min={0}
                max={5}
                step={0.5}
                className={`${controlClassName} pr-10 disabled:bg-gray-50 disabled:text-gray-400`}
                value={typeof liveTradeConfig.max_price_deviation === 'number'
                  ? Number((liveTradeConfig.max_price_deviation * 100).toFixed(2))
                  : 2}
                onChange={(e) => updateLive({ max_price_deviation: Number(e.target.value) / 100 })}
                disabled={liveTradeConfig.order_type !== 'LIMIT'}
              />
              <span className="pointer-events-none absolute inset-y-0 right-4 flex items-center text-sm text-gray-400">%</span>
            </div>
            {fieldError(validationIssues, 'max_price_deviation') && (
              <div className="text-xs text-red-500 mt-1">{fieldError(validationIssues, 'max_price_deviation')}</div>
            )}
          </label>

          <label>
            <div className="mb-1 text-sm">单轮最大委托数</div>
            <input
              type="number"
              min={1}
              max={100}
              className={controlClassName}
              value={liveTradeConfig.max_orders_per_cycle}
              onChange={(e) => updateLive({ max_orders_per_cycle: Number(e.target.value) })}
            />
            {fieldError(validationIssues, 'max_orders_per_cycle') && (
              <div className="text-xs text-red-500 mt-1">{fieldError(validationIssues, 'max_orders_per_cycle')}</div>
            )}
          </label>
        </div>
      </section>

      <section className="rounded-2xl border border-gray-200 p-3.5 md:p-4">
        <div className="mb-2.5 font-semibold text-gray-900">风险保护</div>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <label>
            <div className="mb-1 text-sm">日内大跌拦截</div>
            <div className="relative">
              <input
                type="number"
                min={-10}
                max={-1}
                step={0.5}
                className={`${controlClassName} pr-10`}
                value={typeof executionConfig.max_buy_drop === 'number'
                  ? Number((executionConfig.max_buy_drop * 100).toFixed(2))
                  : -3}
                onChange={(e) => updateExec({ max_buy_drop: Number(e.target.value) / 100 })}
              />
              <span className="pointer-events-none absolute inset-y-0 right-4 flex items-center text-sm text-gray-400">%</span>
            </div>
          </label>

          <label>
            <div className="mb-1 text-sm">全局止损</div>
            <div className="relative">
              <input
                type="number"
                min={-20}
                max={-3}
                step={0.5}
                className={`${controlClassName} pr-10`}
                value={typeof executionConfig.stop_loss === 'number'
                  ? Number((executionConfig.stop_loss * 100).toFixed(2))
                  : -8}
                onChange={(e) => updateExec({ stop_loss: Number(e.target.value) / 100 })}
              />
              <span className="pointer-events-none absolute inset-y-0 right-4 flex items-center text-sm text-gray-400">%</span>
            </div>
          </label>
        </div>
      </section>
    </div>
  );
};

export default LiveTradeConfigForm;

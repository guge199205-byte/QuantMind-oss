import React, { useState, useEffect } from 'react';
import { Settings } from 'lucide-react';
import { Card, CardContent } from './ui/Card';
import { Textarea } from './ui/Textarea';
import { Button } from './ui/Button';
import { TaskConfig } from '../types-v2';
import { alphaAgentService, MarketInfo } from '../services/alphaAgentService';

interface InputPanelProps {
  onSubmit: (config: TaskConfig) => void;
  isRunning: boolean;
}

const MARKET_EMOJI: Record<string, string> = {
  a_share: '🇨🇳',
  crypto: '₿',
  hong_kong: '🇭🇰',
  us_stock: '🇺🇸',
};

export const InputPanel: React.FC<InputPanelProps> = ({ onSubmit, isRunning }) => {
  const [userInput, setUserInput] = useState('');
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [markets, setMarkets] = useState<MarketInfo[]>([]);
  const [config, setConfig] = useState<Partial<TaskConfig>>({
    numDirections: 2,
    maxRounds: 7,
    miningMarket: 'a_share',
    market: 'csi500',
    parallelExecution: true,
    qualityGateEnabled: true,
  });

  useEffect(() => {
    alphaAgentService.listMarkets().then(setMarkets).catch(() => {});
  }, []);

  const handleSubmit = () => {
    if (!userInput.trim()) return;
    onSubmit({
      userInput: userInput.trim(),
      ...config,
    } as TaskConfig);
  };

  const examplePrompts = [
    '请帮我挖掘动量类因子，重点关注短期反转效应和成交量配合',
    '探索价值因子与成长因子的组合策略，考虑行业中性化',
    '基于技术指标构建因子，重点关注RSI和MACD的组合',
  ];

  return (
    <Card className="w-full">
      <CardContent className="p-6">
        <div className="space-y-4">
          {/* Market selector */}
          <div>
            <label className="mb-2 block text-sm font-medium">
              🌍 选择挖掘市场
            </label>
            <div className="flex flex-wrap gap-2">
              {markets.length > 0 ? (
                markets.map((m) => (
                  <button
                    key={m.market_id}
                    onClick={() => setConfig({ ...config, miningMarket: m.market_id as TaskConfig['miningMarket'] })}
                    disabled={isRunning || !m.data_ready}
                    className={`flex items-center gap-1.5 rounded-lg border px-4 py-2 text-sm transition-all ${
                      config.miningMarket === m.market_id
                        ? 'border-primary bg-primary/10 text-primary font-medium'
                        : m.data_ready
                          ? 'border-border bg-background text-muted-foreground hover:border-primary/50 hover:text-foreground'
                          : 'border-border bg-muted/30 text-muted-foreground/50 cursor-not-allowed'
                    }`}
                    title={!m.data_ready ? '数据未就绪' : m.description}
                  >
                    <span>{MARKET_EMOJI[m.market_id] || '📈'}</span>
                    <span>{m.market_name}</span>
                    {!m.data_ready && (
                      <span className="ml-1 rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
                        待接入
                      </span>
                    )}
                  </button>
                ))
              ) : (
                <div className="flex gap-2">
                  {['a_share', 'crypto', 'hong_kong', 'us_stock'].map((mid) => (
                    <button
                      key={mid}
                      onClick={() => setConfig({ ...config, miningMarket: mid as TaskConfig['miningMarket'] })}
                      disabled={isRunning}
                      className={`flex items-center gap-1.5 rounded-lg border px-4 py-2 text-sm transition-all ${
                        config.miningMarket === mid
                          ? 'border-primary bg-primary/10 text-primary font-medium'
                          : 'border-border bg-background text-muted-foreground hover:border-primary/50'
                      }`}
                    >
                      <span>{MARKET_EMOJI[mid] || '📈'}</span>
                      <span>{mid === 'a_share' ? 'A股' : mid === 'crypto' ? '加密货币' : mid === 'hong_kong' ? '港股' : '美股'}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Main input */}
          <div>
            <label className="mb-2 block text-sm font-medium">
              💬 描述你的因子挖掘需求
            </label>
            <Textarea
              value={userInput}
              onChange={(e) => setUserInput(e.target.value)}
              placeholder={
                config.miningMarket === 'crypto'
                  ? '描述你想挖掘的加密货币因子类型，例如：短期动量反转、量价背离、波动率突破...'
                  : '用自然语言描述你想要挖掘的因子类型、策略思路或研究方向...'
              }
              className="min-h-[120px] resize-none text-base"
              disabled={isRunning}
            />
          </div>

          {/* Example prompts */}
          {!userInput && (
            <div className="space-y-2">
              <p className="text-xs text-muted-foreground">💡 示例:</p>
              <div className="space-y-1">
                {(config.miningMarket === 'crypto'
                  ? [
                      '挖掘 BTC 短期动量反转因子，重点关注 5 分钟和 1 小时级别的量价背离',
                      '构建加密货币波动率因子，结合链上数据和交易量变化',
                      '探索 ETH 和 BTC 的相关性因子，用于跨币种套利策略',
                    ]
                  : examplePrompts
                ).map((prompt, idx) => (
                  <button
                    key={idx}
                    onClick={() => setUserInput(prompt)}
                    className="block w-full rounded-md bg-secondary/50 px-3 py-2 text-left text-xs text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Advanced config */}
          <div>
            <button
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="flex items-center gap-2 text-sm text-muted-foreground transition-colors hover:text-foreground"
            >
              <Settings className="h-4 w-4" />
              高级配置
              <span className="text-xs">
                {showAdvanced ? '▲' : '▼'}
              </span>
            </button>

            {showAdvanced && (
              <div className="mt-4 grid grid-cols-2 gap-4 rounded-md border border-border bg-secondary/20 p-4">
                <div>
                  <label className="mb-1 block text-xs text-muted-foreground">
                    并行方向数
                  </label>
                  <input
                    type="number"
                    value={config.numDirections}
                    onChange={(e) =>
                      setConfig({ ...config, numDirections: parseInt(e.target.value) })
                    }
                    className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm"
                    min={1}
                    max={10}
                  />
                </div>

                <div>
                  <label className="mb-1 block text-xs text-muted-foreground">
                    进化轮次
                  </label>
                  <input
                    type="number"
                    value={config.maxRounds}
                    onChange={(e) =>
                      setConfig({ ...config, maxRounds: parseInt(e.target.value) })
                    }
                    className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm"
                    min={1}
                    max={20}
                  />
                </div>

                <div>
                  <label className="mb-1 block text-xs text-muted-foreground">
                    回测市场
                  </label>
                  <select
                    value={config.market}
                    onChange={(e) =>
                      setConfig({ ...config, market: e.target.value as 'csi500' | 'sp500' })
                    }
                    className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm"
                  >
                    <option value="csi500">CSI 500 (中证500)</option>
                    <option value="sp500">S&P 500</option>
                  </select>
                </div>

                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="qualityGate"
                    checked={config.qualityGateEnabled}
                    onChange={(e) =>
                      setConfig({ ...config, qualityGateEnabled: e.target.checked })
                    }
                    className="h-4 w-4 rounded border-input"
                  />
                  <label htmlFor="qualityGate" className="text-xs text-muted-foreground">
                    启用质量门控
                  </label>
                </div>
              </div>
            )}
          </div>

          {/* Action buttons */}
          <div className="flex gap-3">
            <Button
              variant="primary"
              size="lg"
              onClick={handleSubmit}
              disabled={!userInput.trim() || isRunning}
              className="flex-1"
            >
              {isRunning ? (
                <>
                  <span className="mr-2 inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                  执行中...
                </>
              ) : (
                <>🚀 开始执行</>
              )}
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

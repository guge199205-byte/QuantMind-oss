import React, { useState, useRef, useEffect } from 'react';
import { Send, Square, Compass } from 'lucide-react';
import { TaskConfig } from '../types-v2';
import { alphaAgentService, MarketInfo } from '../services/alphaAgentService';

const MARKET_LABELS: Record<string, string> = {
  a_share: 'A股',
  crypto: '加密货币',
  hong_kong: '港股',
  us_stock: '美股',
};

interface ChatInputProps {
  onSubmit: (config: TaskConfig) => void;
  onStop?: () => void;
  isRunning?: boolean;
}

export const ChatInput: React.FC<ChatInputProps> = ({ onSubmit, onStop, isRunning = false }) => {
  const [input, setInput] = useState('');
  const [useCustomMiningDirection, setUseCustomMiningDirection] = useState(false);
  const [miningMarket, setMiningMarket] = useState<string>('a_share');
  const [dataSource, setDataSource] = useState<string>('qlib_bin');
  const [markets, setMarkets] = useState<MarketInfo[]>([]);
  const [config] = useState<Partial<TaskConfig>>({ librarySuffix: '' });
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    alphaAgentService.listMarkets().then(setMarkets).catch(() => {});
  }, []);

  const handleSubmit = () => {
    if (isRunning) return;
    const suffix = config.librarySuffix?.trim() || undefined;
    onSubmit({
      userInput: input.trim(),
      useCustomMiningDirection,
      miningMarket: miningMarket as TaskConfig['miningMarket'],
      dataSource: dataSource as TaskConfig['dataSource'],
      ...config,
      librarySuffix: suffix,
    } as TaskConfig);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = Math.max(52, Math.min(textareaRef.current.scrollHeight, 120)) + 'px';
    }
  }, [input]);

  const marketList = markets.length > 0
    ? markets.map((m) => ({ id: m.market_id, name: m.market_name, ready: m.data_ready }))
    : [
        { id: 'a_share', name: 'A股', ready: true },
        { id: 'crypto', name: '加密货币', ready: true },
        { id: 'hong_kong', name: '港股', ready: false },
        { id: 'us_stock', name: '美股', ready: false },
      ];

  return (
    <div className="fixed left-0 right-0 z-50 pb-2" style={{ bottom: '88px' }}>
      <div className="container mx-auto px-6 max-w-3xl">
        <div className="gradient-border">
          <div className="gradient-border-content">
            <div className="glass-strong rounded-xl p-4">

              {/* Market + Direction row */}
              <div className="flex items-center gap-2 mb-3 flex-wrap">
                {/* Market selector — compact inline buttons */}
                <div className="flex items-center gap-1">
                  <span className="text-xs text-muted-foreground mr-1">市场</span>
                  {marketList.map((m) => (
                    <button
                      key={m.id}
                      onClick={() => setMiningMarket(m.id)}
                      disabled={isRunning || !m.ready}
                      className={`rounded-md px-2.5 py-1 text-xs font-medium transition-all ${
                        miningMarket === m.id
                          ? 'bg-primary/15 text-primary ring-1 ring-primary/30'
                          : m.ready
                            ? 'text-muted-foreground hover:text-foreground hover:bg-secondary/60'
                            : 'text-muted-foreground/30 cursor-not-allowed'
                      }`}
                      title={!m.ready ? '数据未就绪' : `${MARKET_LABELS[m.id]}因子挖掘`}
                    >
                      {m.name}
                      {!m.ready && <span className="ml-0.5 text-[10px] opacity-40">*</span>}
                    </button>
                  ))}
                </div>

                <div className="h-4 w-px bg-border mx-1" />

                {/* Data source selector */}
                <div className="flex items-center gap-1">
                  <span className="text-xs text-muted-foreground mr-1">数据</span>
                  {[
                    { id: 'qlib_bin', name: 'Qlib' },
                    { id: 'parquet', name: 'Parquet' },
                    { id: 'pg', name: 'PG' },
                  ].map((ds) => (
                    <button
                      key={ds.id}
                      onClick={() => setDataSource(ds.id)}
                      disabled={isRunning}
                      className={`rounded-md px-2 py-1 text-xs font-medium transition-all ${
                        dataSource === ds.id
                          ? 'bg-primary/15 text-primary ring-1 ring-primary/30'
                          : 'text-muted-foreground hover:text-foreground hover:bg-secondary/60'
                      }`}
                    >
                      {ds.name}
                    </button>
                  ))}
                </div>

                <div className="h-4 w-px bg-border mx-1" />

                {/* Direction toggle */}
                <button
                  type="button"
                  onClick={() => setUseCustomMiningDirection(!useCustomMiningDirection)}
                  title={useCustomMiningDirection ? '使用设置中的挖掘方向（已开）' : '使用设置中的挖掘方向（点击开启）'}
                  className={`flex items-center gap-1 rounded-md px-2 py-1 text-xs transition-all ${
                    useCustomMiningDirection
                      ? 'bg-primary/15 text-primary ring-1 ring-primary/30'
                      : 'text-muted-foreground hover:text-foreground hover:bg-secondary/60'
                  }`}
                >
                  <Compass className="h-3.5 w-3.5" />
                  <span>自选方向</span>
                </button>
              </div>

              {/* Textarea + send */}
              <div className="flex items-end gap-3">
                <div className="flex-1">
                  <textarea
                    ref={textareaRef}
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder={
                      isRunning
                        ? '实验运行中...可切换页面，任务不会中断'
                        : useCustomMiningDirection
                          ? '已开启自选挖掘方向，将使用「设置 → 挖掘方向」中的选项'
                          : miningMarket === 'crypto'
                            ? '描述加密货币因子需求，如：短期动量反转、量价背离...'
                            : '描述因子挖掘需求 (Enter 发送，Shift+Enter 换行)'
                    }
                    disabled={isRunning}
                    className="w-full bg-transparent text-base placeholder:text-muted-foreground focus:outline-none resize-none"
                    rows={2}
                    style={{ minHeight: '52px', maxHeight: '120px' }}
                  />
                </div>

                <div className="flex items-center gap-2">
                  {isRunning && onStop ? (
                    <button
                      onClick={onStop}
                      className="p-2.5 rounded-lg bg-red-500 text-white hover:bg-red-600 transition-all hover:scale-105 active:scale-95"
                      title="中断实验"
                    >
                      <Square className="h-5 w-5" />
                    </button>
                  ) : (
                    <button
                      onClick={handleSubmit}
                      disabled={isRunning}
                      className="p-2.5 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-all hover:scale-105 active:scale-95"
                      title="发送 (Enter)"
                    >
                      <Send className="h-5 w-5" />
                    </button>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

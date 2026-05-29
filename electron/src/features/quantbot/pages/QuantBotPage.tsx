/**
 * QuantBot 主页面 — 完整嵌入 QwenPaw 智能体 Web 界面
 *
 * QwenPaw 是项目的大脑，提供完整 AI 智能体能力：
 * 执行命令、写代码、跑回测、跑因子挖掘、获取股票数据 AI 分析、获取新闻数据等。
 *
 * 加载策略：
 * - Electron 桌面端：直接访问 http://127.0.0.1:8089（QwenPaw 容器宿主映射端口）
 * - Web 浏览器端：通过 API 网关 /api/v1/qwenpaw-ui/ 反向代理
 */

import React, { useEffect, useMemo, useRef, useState, useCallback } from 'react';
import { Bot, RefreshCw, Wifi, WifiOff, ExternalLink } from 'lucide-react';
import { isElectronEnv, getDynamicServerUrl } from '../../../config/services';

const QWENPAW_DESKTOP_URL = 'http://127.0.0.1:8089/';

const QuantBotPage: React.FC = () => {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [iframeKey, setIframeKey] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [connected, setConnected] = useState<boolean>(false);

  const embedUrl = useMemo(() => {
    if (isElectronEnv()) {
      return QWENPAW_DESKTOP_URL;
    }
    const base = getDynamicServerUrl() || '';
    if (base) {
      return `${base.replace(/\/+$/, '')}/api/v1/qwenpaw-ui/`;
    }
    if (typeof window !== 'undefined') {
      return `${window.location.origin}/api/v1/qwenpaw-ui/`;
    }
    return '/api/v1/qwenpaw-ui/';
  }, []);

  const handleReload = useCallback(() => {
    setLoading(true);
    setConnected(false);
    setIframeKey(iframeKey + 1);
  }, []);

  const handleOpenExternal = useCallback(() => {
    if (isElectronEnv()) {
      window.open(QWENPAW_DESKTOP_URL, '_blank');
    } else {
      window.open(embedUrl, '_blank');
    }
  }, [embedUrl]);

  useEffect(() => {
    setLoading(true);
    setConnected(false);
  }, [iframeKey]);

  return (
    <div className="w-full h-full flex flex-col overflow-hidden bg-[#1a1a1a]">
      {/* 顶部工具栏 — 极简，最大保留内容区域 */}
      <div className="h-[40px] flex-shrink-0 bg-[#1e1e1e] border-b border-[#333] flex items-center justify-between px-4">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
            <Bot className="w-4 h-4 text-white" />
          </div>
          <span className="text-sm font-medium text-gray-300">QuantBot · QwenPaw</span>
        </div>

        <div className="flex items-center gap-2">
          <div className={`flex items-center gap-1 text-xs ${connected ? 'text-emerald-400' : loading ? 'text-amber-400' : 'text-red-400'}`}>
            {connected ? <Wifi className="w-3.5 h-3.5" /> : loading ? <div className="w-3.5 h-3.5 border-2 border-amber-400 border-t-transparent rounded-full animate-spin" /> : <WifiOff className="w-3.5 h-3.5" />}
            <span>{connected ? '已连接' : loading ? '连接中…' : '断开'}</span>
          </div>
          <button
            onClick={handleOpenExternal}
            className="flex items-center gap-1 rounded px-2 py-1 text-xs text-gray-400 hover:text-gray-200 hover:bg-[#333] transition-colors"
            title="在外部浏览器打开"
          >
            <ExternalLink className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={handleReload}
            className="flex items-center gap-1 rounded px-2 py-1 text-xs text-gray-400 hover:text-gray-200 hover:bg-[#333] transition-colors"
            title="重新加载"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* iframe 内容区域— 无缝全屏嵌入 */}
      <div className="flex-1 relative overflow-hidden bg-[#1a1a1a]">
        {loading && (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-[#1a1a1a]">
            <div className="flex flex-col items-center gap-4">
              <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
              <div className="text-center">
                <p className="text-sm text-gray-400">QwenPaw 智能体加载中…</p>
                <p className="text-xs text-gray-500 mt-1">AI Brain · Code · Backtest · Factor · Data</p>
              </div>
            </div>
          </div>
        )}
        <iframe
          ref={iframeRef}
          key={iframeKey}
          src={embedUrl}
          className="w-full h-full border-0"
          title="QwenPaw Agent"
          allow="clipboard-read; clipboard-write; fullscreen; microphone; camera"
          sandbox="allow-scripts allow-same-origin allow-forms allow-downloads allow-popups allow-popups-to-escape-sandbox allow-modals allow-presentation"
          onLoad={() => {
            setLoading(false);
            setConnected(true);
          }}
        />
      </div>
    </div>
  );
};

export default QuantBotPage;
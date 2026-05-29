/** TradingAgents main page — stock input, progress, report */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { StockInput } from '../components/StockInput';
import { LLMConfig } from '../components/LLMConfig';
import { ProgressPanel } from '../components/ProgressPanel';
import { ReportViewer } from '../components/ReportViewer';
import { HistoryList } from '../components/HistoryList';
import {
  startAnalysis,
  getProgress,
  getReport,
  getHistory,
  stopAnalysis,
} from '../services/tradingAgentsService';
import type { AnalysisProgress, AnalysisHistoryItem } from '../types';

type ViewState = 'idle' | 'running' | 'complete' | 'error';

const TradingAgentsPage: React.FC = () => {
  // Input state
  const [ticker, setTicker] = useState('');
  const [tradeDate, setTradeDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [provider, setProvider] = useState('minimax');
  const [quickModel, setQuickModel] = useState('MiniMax-M2.7-highspeed');
  const [deepModel, setDeepModel] = useState('MiniMax-M2.7');

  // Analysis state
  const [viewState, setViewState] = useState<ViewState>('idle');
  const [analysisId, setAnalysisId] = useState<string | null>(null);
  const [progress, setProgress] = useState<AnalysisProgress | null>(null);
  const [errorMsg, setErrorMsg] = useState('');
  const [history, setHistory] = useState<AnalysisHistoryItem[]>([]);

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Load history on mount
  useEffect(() => {
    getHistory(20)
      .then((data) => setHistory(data.history))
      .catch(() => {});
  }, []);

  // Poll progress when running
  useEffect(() => {
    if (viewState !== 'running' || !analysisId) {
      if (pollRef.current) clearInterval(pollRef.current);
      return;
    }

    pollRef.current = setInterval(async () => {
      try {
        const p = await getProgress(analysisId);
        setProgress(p);

        if (p.is_complete) {
          setViewState('complete');
          if (pollRef.current) clearInterval(pollRef.current);
          getHistory(20).then((d) => setHistory(d.history)).catch(() => {});
        }
        if (p.error) {
          setErrorMsg(p.error);
          setViewState('error');
          if (pollRef.current) clearInterval(pollRef.current);
        }
      } catch (err) {
        // Network error — keep polling
      }
    }, 2000);

    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [viewState, analysisId]);

  const handleStart = useCallback(async () => {
    if (!ticker.trim()) return;

    try {
      setViewState('running');
      setErrorMsg('');
      setProgress(null);

      const result = await startAnalysis({
        ticker: ticker.trim(),
        trade_date: tradeDate,
        llm_provider: provider,
        quick_think_llm: quickModel,
        deep_think_llm: deepModel,
      });

      setAnalysisId(result.analysis_id);
    } catch (err: any) {
      setErrorMsg(err.message || '启动失败');
      setViewState('error');
    }
  }, [ticker, tradeDate, provider, quickModel, deepModel]);

  const handleStop = useCallback(async () => {
    if (!analysisId) return;
    try {
      await stopAnalysis(analysisId);
    } catch {}
    setErrorMsg('用户手动停止');
    setViewState('error');
  }, [analysisId]);

  const handleReset = useCallback(() => {
    setViewState('idle');
    setAnalysisId(null);
    setProgress(null);
    setErrorMsg('');
  }, []);

  const handleHistorySelect = useCallback(async (item: AnalysisHistoryItem) => {
    try {
      const report = await getReport(item.analysis_id);
      setProgress({
        ticker: report.ticker,
        trade_date: report.trade_date,
        is_running: false,
        is_complete: true,
        current_stage: '',
        completed_stages: [],
        stage_reports: report.stage_reports,
        signal: report.signal,
        final_state: report.final_state,
        stats: report.stats,
        elapsed: report.elapsed,
      });
      setTicker(report.ticker);
      setTradeDate(report.trade_date);
      setAnalysisId(item.analysis_id);
      setViewState('complete');
    } catch (err: any) {
      setErrorMsg(err.message || '加载失败');
      setViewState('error');
    }
  }, []);

  return (
    <div style={{
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 100%)',
      color: '#1e293b',
      fontFamily: "'Inter', -apple-system, sans-serif",
    }}>
      <div style={{
        display: 'flex',
        maxWidth: 1400,
        margin: '0 auto',
        padding: '24px 20px',
        gap: 24,
      }}>
        {/* Left Sidebar */}
        <div style={{
          width: 280,
          flexShrink: 0,
          display: 'flex',
          flexDirection: 'column',
          gap: 16,
        }}>
          {/* Title */}
          <div style={{ textAlign: 'center', marginBottom: 4 }}>
            <div style={{ fontSize: 22, fontWeight: 800 }}>
              <span style={{ color: '#ff5a1f' }}>Trading</span>
              <span style={{ color: '#1e293b' }}>Agents</span>
            </div>
            <div style={{ fontSize: 12, color: '#64748b', marginTop: 2 }}>
              A股多Agent投研分析
            </div>
          </div>

          {/* Input Section */}
          <div style={{
            background: 'rgba(255,255,255,0.8)',
            borderRadius: 12,
            border: '1px solid rgba(226,232,250,0.8)',
            padding: 16,
            backdropFilter: 'blur(8px)',
          }}>
            <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 14, color: '#1e293b' }}>
              新建分析
            </div>
            <StockInput
              ticker={ticker}
              tradeDate={tradeDate}
              disabled={viewState === 'running'}
              onTickerChange={setTicker}
              onDateChange={setTradeDate}
            />
            <div style={{ marginTop: 14 }}>
              <LLMConfig
                provider={provider}
                quickModel={quickModel}
                deepModel={deepModel}
                onProviderChange={setProvider}
                onQuickModelChange={setQuickModel}
                onDeepModelChange={setDeepModel}
              />
            </div>
            <div style={{ marginTop: 16, display: 'flex', gap: 8 }}>
              {viewState === 'running' ? (
                <button
                  onClick={handleStop}
                  style={{
                    flex: 1,
                    padding: '10px 16px',
                    background: '#ef4444',
                    border: 'none',
                    borderRadius: 8,
                    color: '#fff',
                    fontWeight: 700,
                    fontSize: 14,
                    cursor: 'pointer',
                  }}
                >
                  停止
                </button>
              ) : (
                <button
                  onClick={viewState === 'idle' ? handleStart : handleReset}
                  disabled={viewState === 'idle' && !ticker.trim()}
                  style={{
                    flex: 1,
                    padding: '10px 16px',
                    background: (!ticker.trim() && viewState === 'idle') ? '#cbd5e1' : 'linear-gradient(135deg, #ff5a1f, #ff8c42)',
                    border: 'none',
                    borderRadius: 8,
                    color: '#fff',
                    fontWeight: 700,
                    fontSize: 14,
                    cursor: (!ticker.trim() && viewState === 'idle') ? 'not-allowed' : 'pointer',
                    boxShadow: (!ticker.trim() && viewState === 'idle') ? 'none' : '0 4px 15px rgba(255,90,31,0.3)',
                  }}
                >
                  {viewState === 'idle' ? '开始分析' : '新建分析'}
                </button>
              )}
            </div>
          </div>

          {/* History */}
          <div style={{
            background: 'rgba(255,255,255,0.8)',
            borderRadius: 12,
            border: '1px solid rgba(226,232,250,0.8)',
            padding: 16,
            backdropFilter: 'blur(8px)',
          }}>
            <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 12, color: '#1e293b' }}>
              历史记录
            </div>
            <HistoryList history={history} onSelect={handleHistorySelect} />
          </div>

          <div style={{ fontSize: 11, color: '#94a3b8', textAlign: 'center', marginTop: 'auto' }}>
            仅供学习研究，不构成投资建议
          </div>
        </div>

        {/* Main Content */}
        <div style={{ flex: 1, minWidth: 0 }}>
          {viewState === 'idle' && <WelcomeView />}

          {viewState === 'running' && progress && (
            <ProgressPanel progress={progress} />
          )}
          {viewState === 'running' && !progress && (
            <div style={{ textAlign: 'center', padding: '120px 0', color: '#64748b' }}>
              <div style={{ fontSize: 32, marginBottom: 16 }}>⏳</div>
              <div>正在启动分析...</div>
            </div>
          )}

          {viewState === 'complete' && progress && (
            <ReportViewer progress={progress} />
          )}

          {viewState === 'error' && (
            <div style={{ textAlign: 'center', padding: '120px 0' }}>
              <div style={{ fontSize: 48, marginBottom: 16 }}>❌</div>
              <div style={{ fontSize: 18, color: '#ef4444', marginBottom: 8 }}>分析失败</div>
              <div style={{ color: '#64748b', fontSize: 14, maxWidth: 400, margin: '0 auto' }}>
                {errorMsg}
              </div>
              <button
                onClick={handleReset}
                style={{
                  marginTop: 24,
                  padding: '10px 24px',
                  background: 'rgba(255,255,255,0.8)',
                  border: '1px solid #e2e8f0',
                  borderRadius: 8,
                  color: '#1e293b',
                  cursor: 'pointer',
                  fontSize: 14,
                }}
              >
                重试
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

/** Welcome / idle view */
const WelcomeView: React.FC = () => (
  <div style={{
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: '60vh',
    textAlign: 'center',
  }}>
    <div style={{ fontSize: 48, marginBottom: 16 }}>📈</div>
    <div style={{ fontSize: 28, fontWeight: 900, marginBottom: 8 }}>
      <span style={{ color: '#ff5a1f' }}>Trading</span>
      <span style={{ color: '#1e293b' }}>Agents</span>
      <span style={{ color: '#1e293b' }}>-</span>
      <span style={{ color: '#ff5a1f' }}>Astock</span>
    </div>
    <div style={{ color: '#64748b', fontSize: 15, maxWidth: 500, lineHeight: 1.7 }}>
      A股多Agent投研分析系统<br />
      7位AI分析师 → 质量门控 → 多空辩论 → 风控评估 → 最终决策
    </div>
    <div style={{
      marginTop: 32,
      padding: '12px 24px',
      border: '1px solid #e2e8f0',
      borderRadius: 12,
      color: '#94a3b8',
      fontSize: 14,
      background: 'rgba(255,255,255,0.6)',
    }}>
      ← 在左侧输入股票代码，开始分析
    </div>
  </div>
);

export default TradingAgentsPage;

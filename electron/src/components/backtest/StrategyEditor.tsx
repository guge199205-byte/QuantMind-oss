/**
 * 策略编辑器组件
 * 使用Monaco Editor进行策略代码编辑
 */

import React, { useState, useRef } from 'react';
import Editor from '@monaco-editor/react';
import { AlertCircle } from 'lucide-react';
import { Strategy, StrategyParameter } from '../../types/backtest';
import { getAllStrategyTemplates } from '../../services/backtest';

interface StrategyEditorProps {
  strategy?: Strategy;
  onSave?: (strategy: Strategy) => void;
  onTest?: (strategy: Strategy) => void;
}

export const StrategyEditor: React.FC<StrategyEditorProps> = ({
  strategy: initialStrategy,
  onSave,
  onTest
}) => {
  const [strategy, setStrategy] = useState<Strategy>(
    initialStrategy || {
      name: '新策略',
      version: '1.0.0',
      description: '',
      parameters: [],
      code: defaultStrategyCode,
      onBar: () => {}
    }
  );

  const [activeTab, setActiveTab] = useState<'code' | 'parameters'>('code');
  const editorRef = useRef<any>(null);

  const handleEditorDidMount = (editor: any) => {
    editorRef.current = editor;
  };

  const handleCodeChange = (value: string | undefined) => {
    if (value !== undefined) {
      setStrategy({ ...strategy, code: value });
    }
  };

  const handleParameterChange = (index: number, field: keyof StrategyParameter, value: any) => {
    setStrategy({
      ...strategy,
      parameters: strategy.parameters.map((param, i) =>
        i === index ? { ...param, [field]: value } : param
      )
    });
  };

  const handleAddParameter = () => {
    setStrategy({
      ...strategy,
      parameters: [
        ...strategy.parameters,
        {
          name: `param${strategy.parameters.length + 1}`,
          type: 'number',
          value: 0,
          description: ''
        }
      ]
    });
  };

  const handleRemoveParameter = (index: number) => {
    setStrategy({
      ...strategy,
      parameters: strategy.parameters.filter((_, i) => i !== index)
    });
  };

  const handleLoadTemplate = (templateName: string) => {
    const templates = getAllStrategyTemplates();
    const template = templates.find(t => t.name === templateName);

    if (template) {
      setStrategy({
        ...template,
        code: template.code || defaultStrategyCode
      });
    }
  };

  const handleSave = () => {
    if (onSave) {
      onSave(strategy);
    }
  };

  const handleTest = () => {
    if (onTest) {
      onTest(strategy);
    }
  };

  return (
    <div className="strategy-editor">
      {/* 头部 */}
      <div className="editor-header">
        <div className="strategy-info">
          <input
            type="text"
            value={strategy.name}
            onChange={e => setStrategy({ ...strategy, name: e.target.value })}
            className="strategy-name-input"
            placeholder="策略名称"
          />
          <input
            type="text"
            value={strategy.version}
            onChange={e => setStrategy({ ...strategy, version: e.target.value })}
            className="strategy-version-input"
            placeholder="版本号"
          />
        </div>

        <div className="editor-actions">
          <select
            onChange={e => handleLoadTemplate(e.target.value)}
            className="template-select"
          >
            <option value="">选择模板...</option>
            {getAllStrategyTemplates().map(t => (
              <option key={t.name} value={t.name}>{t.name}</option>
            ))}
          </select>

          <button onClick={handleTest} className="btn-test">
            测试策略
          </button>
          <button onClick={handleSave} className="btn-save">
            保存策略
          </button>
        </div>
      </div>

      {/* 描述 */}
      <div className="strategy-description">
        <div className="warning-banner" style={{
          display: 'flex',
          gap: '12px',
          padding: '12px',
          marginBottom: '12px',
          backgroundColor: 'rgba(234, 179, 8, 0.1)',
          border: '1px solid rgba(234, 179, 8, 0.3)',
          borderRadius: '4px',
          color: '#fcd34d'
        }}>
          <AlertCircle size={20} />
          <div style={{ fontSize: '14px' }}>
            <div style={{ fontWeight: 600, marginBottom: '2px' }}>注意</div>
            <div>当前仅支持Qlib预设策略，代码编辑功能暂不可用。请使用策略参数配置器进行调整。</div>
          </div>
        </div>
        <textarea
          value={strategy.description || ''}
          onChange={e => setStrategy({ ...strategy, description: e.target.value })}
          placeholder="策略描述..."
          rows={2}
        />
      </div>

      {/* 标签页 */}
      <div className="editor-tabs">
        <button
          className={`tab ${activeTab === 'code' ? 'active' : ''}`}
          onClick={() => setActiveTab('code')}
        >
          代码编辑
        </button>
        <button
          className={`tab ${activeTab === 'parameters' ? 'active' : ''}`}
          onClick={() => setActiveTab('parameters')}
        >
          参数配置
        </button>
      </div>

      {/* 内容区域 */}
      <div className="editor-content">
        {activeTab === 'code' && (
          <div className="code-editor-container">
            <Editor
              height="500px"
              defaultLanguage="javascript"
              value={strategy.code}
              onChange={handleCodeChange}
              onMount={handleEditorDidMount}
              theme="vs-dark"
              options={{
                readOnly: true, // Qlib专用化：禁止代码编辑
                minimap: { enabled: true },
                fontSize: 14,
                lineNumbers: 'on',
                scrollBeyondLastLine: false,
                automaticLayout: true,
                tabSize: 2,
                wordWrap: 'on'
              }}
            />

            {/* 代码提示 */}
            <div className="code-hints">
              <h4>可用API:</h4>
              <ul>
                <li><code>context.buy(size, price?)</code> - 买入</li>
                <li><code>context.sell(size, price?)</code> - 卖出</li>
                <li><code>context.closePosition()</code> - 平仓</li>
                <li><code>context.position</code> - 当前持仓</li>
                <li><code>context.capital</code> - 可用资金</li>
                <li><code>context.equity</code> - 总权益</li>
                <li><code>context.indicators.sma(period)</code> - 简单移动平均</li>
                <li><code>context.indicators.ema(period)</code> - 指数移动平均</li>
                <li><code>context.indicators.rsi(period)</code> - RSI指标</li>
                <li><code>context.indicators.macd()</code> - MACD指标</li>
                <li><code>context.indicators.bollinger(period, stdDev)</code> - 布林带</li>
                <li><code>context.indicators.atr(period)</code> - ATR指标</li>
              </ul>
            </div>
          </div>
        )}

        {activeTab === 'parameters' && (
          <div className="parameters-panel">
            <div className="parameters-header">
              <h3>策略参数</h3>
              <button onClick={handleAddParameter} className="btn-add">
                + 添加参数
              </button>
            </div>

            <div className="parameters-list">
              {strategy.parameters.map((param, index) => (
                <div key={index} className="parameter-item">
                  <div className="param-row">
                    <input
                      type="text"
                      value={param.name}
                      onChange={e => handleParameterChange(index, 'name', e.target.value)}
                      placeholder="参数名"
                      className="param-name"
                    />

                    <select
                      value={param.type}
                      onChange={e => handleParameterChange(index, 'type', e.target.value)}
                      className="param-type"
                    >
                      <option value="number">数字</option>
                      <option value="string">字符串</option>
                      <option value="boolean">布尔值</option>
                    </select>

                    {param.type === 'number' && (
                      <>
                        <input
                          type="number"
                          value={param.value}
                          onChange={e => handleParameterChange(index, 'value', Number(e.target.value))}
                          placeholder="默认值"
                          className="param-value"
                        />
                        <input
                          type="number"
                          value={param.min || ''}
                          onChange={e => handleParameterChange(index, 'min', Number(e.target.value))}
                          placeholder="最小值"
                          className="param-min"
                        />
                        <input
                          type="number"
                          value={param.max || ''}
                          onChange={e => handleParameterChange(index, 'max', Number(e.target.value))}
                          placeholder="最大值"
                          className="param-max"
                        />
                        <input
                          type="number"
                          value={param.step || ''}
                          onChange={e => handleParameterChange(index, 'step', Number(e.target.value))}
                          placeholder="步长"
                          className="param-step"
                        />
                      </>
                    )}

                    {param.type === 'string' && (
                      <input
                        type="text"
                        value={param.value}
                        onChange={e => handleParameterChange(index, 'value', e.target.value)}
                        placeholder="默认值"
                        className="param-value"
                      />
                    )}

                    {param.type === 'boolean' && (
                      <input
                        type="checkbox"
                        checked={param.value}
                        onChange={e => handleParameterChange(index, 'value', e.target.checked)}
                        className="param-value"
                      />
                    )}

                    <button
                      onClick={() => handleRemoveParameter(index)}
                      className="btn-remove"
                    >
                      删除
                    </button>
                  </div>

                  <div className="param-description">
                    <input
                      type="text"
                      value={param.description || ''}
                      onChange={e => handleParameterChange(index, 'description', e.target.value)}
                      placeholder="参数描述..."
                      className="param-desc-input"
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      <style>{`
        .strategy-editor {
          display: flex;
          flex-direction: column;
          height: 100%;
          background: #1e1e1e;
          color: #d4d4d4;
        }

        .editor-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 16px;
          background: #252526;
          border-bottom: 1px solid #3e3e42;
        }

        .strategy-info {
          display: flex;
          gap: 12px;
        }

        .strategy-name-input,
        .strategy-version-input {
          background: #3c3c3c;
          border: 1px solid #555;
          color: #d4d4d4;
          padding: 8px 12px;
          border-radius: 4px;
          font-size: 14px;
        }

        .strategy-name-input {
          width: 250px;
          font-weight: 600;
        }

        .strategy-version-input {
          width: 100px;
        }

        .editor-actions {
          display: flex;
          gap: 8px;
        }

        .template-select,
        .btn-test,
        .btn-save {
          padding: 8px 16px;
          border-radius: 4px;
          border: none;
          cursor: pointer;
          font-size: 14px;
        }

        .template-select {
          background: #3c3c3c;
          color: #d4d4d4;
          border: 1px solid #555;
        }

        .btn-test {
          background: #0e639c;
          color: white;
        }

        .btn-test:hover {
          background: #1177bb;
        }

        .btn-save {
          background: #0e8a16;
          color: white;
        }

        .btn-save:hover {
          background: #2ea043;
        }

        .strategy-description {
          padding: 12px 16px;
          background: #252526;
          border-bottom: 1px solid #3e3e42;
        }

        .strategy-description textarea {
          width: 100%;
          background: #3c3c3c;
          border: 1px solid #555;
          color: #d4d4d4;
          padding: 8px;
          border-radius: 4px;
          font-size: 13px;
          resize: none;
        }

        .editor-tabs {
          display: flex;
          background: #252526;
          border-bottom: 1px solid #3e3e42;
        }

        .tab {
          padding: 12px 24px;
          background: transparent;
          border: none;
          color: #969696;
          cursor: pointer;
          border-bottom: 2px solid transparent;
          font-size: 14px;
        }

        .tab.active {
          color: #d4d4d4;
          border-bottom-color: #0e639c;
        }

        .editor-content {
          flex: 1;
          overflow: auto;
        }

        .code-editor-container {
          display: flex;
          gap: 16px;
          padding: 16px;
        }

        .code-hints {
          min-width: 300px;
          background: #252526;
          padding: 16px;
          border-radius: 4px;
          font-size: 13px;
        }

        .code-hints h4 {
          margin: 0 0 12px 0;
          color: #4ec9b0;
        }

        .code-hints ul {
          list-style: none;
          padding: 0;
          margin: 0;
        }

        .code-hints li {
          margin-bottom: 8px;
          line-height: 1.6;
        }

        .code-hints code {
          color: #ce9178;
          font-family: var(--font-mono);
        }

        .parameters-panel {
          padding: 16px;
        }

        .parameters-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 16px;
        }

        .parameters-header h3 {
          margin: 0;
          color: #d4d4d4;
        }

        .btn-add {
          padding: 6px 12px;
          background: #0e639c;
          color: white;
          border: none;
          border-radius: 4px;
          cursor: pointer;
          font-size: 13px;
        }

        .parameters-list {
          display: flex;
          flex-direction: column;
          gap: 16px;
        }

        .parameter-item {
          background: #252526;
          padding: 16px;
          border-radius: 4px;
          border: 1px solid #3e3e42;
        }

        .param-row {
          display: flex;
          gap: 8px;
          align-items: center;
          margin-bottom: 8px;
        }

        .param-row input,
        .param-row select {
          background: #3c3c3c;
          border: 1px solid #555;
          color: #d4d4d4;
          padding: 6px 10px;
          border-radius: 4px;
          font-size: 13px;
        }

        .param-name {
          flex: 1;
        }

        .param-type {
          width: 100px;
        }

        .param-value,
        .param-min,
        .param-max,
        .param-step {
          width: 80px;
        }

        .btn-remove {
          padding: 6px 12px;
          background: #a12626;
          color: white;
          border: none;
          border-radius: 4px;
          cursor: pointer;
          font-size: 13px;
        }

        .param-description {
          margin-top: 8px;
        }

        .param-desc-input {
          width: 100%;
          background: #3c3c3c;
          border: 1px solid #555;
          color: #d4d4d4;
          padding: 6px 10px;
          border-radius: 4px;
          font-size: 13px;
        }
      `}</style>
    </div>
  );
};

const defaultStrategyCode = `/**
 * 策略函数
 * @param {OHLCV} bar - 当前K线数据
 * @param {StrategyContext} context - 策略上下文
 */
function onBar(bar, context) {
  // 获取指标
  const sma20 = context.indicators.sma(20);
  const sma50 = context.indicators.sma(50);

  // 获取当前索引
  const index = context.barIndex;

  // 策略逻辑
  if (index < 50) return; // 等待指标计算完成

  // 金叉买入
  if (sma20[index] > sma50[index] &&
      sma20[index - 1] <= sma50[index - 1] &&
      !context.position) {
    const size = Math.floor(context.capital / bar.close);
    context.buy(size);
  }

  // 死叉卖出
  if (sma20[index] < sma50[index] &&
      sma20[index - 1] >= sma50[index - 1] &&
      context.position) {
    context.closePosition();
  }
}
`;

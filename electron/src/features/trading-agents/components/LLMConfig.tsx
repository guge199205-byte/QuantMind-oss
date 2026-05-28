/** LLM provider and model selection */

import React, { useEffect, useState } from 'react';
import type { LLMProvider } from '../types';
import { getConfig } from '../services/tradingAgentsService';

interface LLMConfigProps {
  provider: string;
  quickModel: string;
  deepModel: string;
  onProviderChange: (v: string) => void;
  onQuickModelChange: (v: string) => void;
  onDeepModelChange: (v: string) => void;
}

export const LLMConfig: React.FC<LLMConfigProps> = ({
  provider,
  quickModel,
  deepModel,
  onProviderChange,
  onQuickModelChange,
  onDeepModelChange,
}) => {
  const [providers, setProviders] = useState<LLMProvider[]>([]);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    getConfig()
      .then((data) => setProviders(data.providers))
      .catch(() => {
        setProviders([
          {
            key: 'minimax',
            quick_models: [{ label: 'MiniMax-M2.7-highspeed', value: 'MiniMax-M2.7-highspeed' }],
            deep_models: [{ label: 'MiniMax-M2.7', value: 'MiniMax-M2.7' }],
          },
          {
            key: 'deepseek',
            quick_models: [{ label: 'DeepSeek V3.2', value: 'deepseek-chat' }],
            deep_models: [{ label: 'DeepSeek V4 Pro', value: 'deepseek-v4-pro' }],
          },
          {
            key: 'openai',
            quick_models: [{ label: 'GPT-5.4 Mini', value: 'gpt-5.4-mini' }],
            deep_models: [{ label: 'GPT-5.4', value: 'gpt-5.4' }],
          },
        ]);
      });
  }, []);

  const currentProvider = providers.find((p) => p.key === provider);

  // Auto-select first model when provider changes
  useEffect(() => {
    if (currentProvider) {
      const quickValid = currentProvider.quick_models.some((m) => m.value === quickModel);
      const deepValid = currentProvider.deep_models.some((m) => m.value === deepModel);
      if (!quickValid && currentProvider.quick_models.length > 0) {
        onQuickModelChange(currentProvider.quick_models[0].value);
      }
      if (!deepValid && currentProvider.deep_models.length > 0) {
        onDeepModelChange(currentProvider.deep_models[0].value);
      }
    }
  }, [provider, currentProvider]);

  const selectStyle: React.CSSProperties = {
    width: '100%',
    padding: '8px 10px',
    background: '#fff',
    border: '1px solid #e2e8f0',
    borderRadius: 8,
    color: '#1e293b',
    fontSize: 13,
    outline: 'none',
  };

  return (
    <div>
      <button
        onClick={() => setExpanded(!expanded)}
        style={{
          background: 'none',
          border: 'none',
          color: '#64748b',
          cursor: 'pointer',
          fontSize: 13,
          padding: 0,
          display: 'flex',
          alignItems: 'center',
          gap: 4,
        }}
      >
        ⚙️ 模型配置 {expanded ? '▲' : '▼'}
      </button>

      {expanded && (
        <div style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div>
            <label style={{ display: 'block', fontSize: 12, color: '#94a3b8', marginBottom: 3 }}>
              LLM 供应商
            </label>
            <select
              value={provider}
              onChange={(e) => onProviderChange(e.target.value)}
              style={selectStyle}
            >
              {providers.map((p) => (
                <option key={p.key} value={p.key}>
                  {p.key}
                </option>
              ))}
            </select>
          </div>

          {currentProvider && (
            <>
              <div>
                <label style={{ display: 'block', fontSize: 12, color: '#94a3b8', marginBottom: 3 }}>
                  快速思考模型
                </label>
                <select
                  value={quickModel}
                  onChange={(e) => onQuickModelChange(e.target.value)}
                  style={selectStyle}
                >
                  {currentProvider.quick_models.map((m) => (
                    <option key={m.value} value={m.value}>
                      {m.label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label style={{ display: 'block', fontSize: 12, color: '#94a3b8', marginBottom: 3 }}>
                  深度思考模型
                </label>
                <select
                  value={deepModel}
                  onChange={(e) => onDeepModelChange(e.target.value)}
                  style={selectStyle}
                >
                  {currentProvider.deep_models.map((m) => (
                    <option key={m.value} value={m.value}>
                      {m.label}
                    </option>
                  ))}
                </select>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
};

import React, { useState, useEffect } from 'react';
import { message, Input, Button, Spin, Select } from 'antd';
import { Key, Save, Eye, EyeOff, CheckCircle, AlertCircle, Trash2 } from 'lucide-react';
import { userCenterService } from '../services/userCenterService';

interface OtherSettingsProps {
  userId: string;
  tenantId: string;
}

const MODEL_PRESETS = [
  { label: 'GLM-5.1 (SiliconFlow)', value: 'Pro/zai-org/GLM-5.1', baseUrl: 'https://api.siliconflow.cn/v1' },
  { label: 'DeepSeek-V3', value: 'deepseek-chat', baseUrl: 'https://api.deepseek.com/v1' },
  { label: 'DeepSeek-R1 (推理)', value: 'deepseek-reasoner', baseUrl: 'https://api.deepseek.com/v1' },
  { label: 'Qwen-Max (通义千问)', value: 'qwen-max', baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1' },
  { label: 'Qwen-Plus', value: 'qwen-plus', baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1' },
  { label: 'GPT-4o', value: 'gpt-4o', baseUrl: 'https://api.openai.com/v1' },
  { label: 'GPT-4o-mini', value: 'gpt-4o-mini', baseUrl: 'https://api.openai.com/v1' },
  { label: 'Claude Sonnet 4', value: 'claude-sonnet-4-20250514', baseUrl: 'https://api.anthropic.com/v1' },
  { label: '自定义', value: '__custom__', baseUrl: '' },
];

export const OtherSettings: React.FC<OtherSettingsProps> = ({ userId, tenantId }) => {
  const [apiKey, setApiKey] = useState('');
  const [maskedKey, setMaskedKey] = useState('');
  const [hasKey, setHasKey] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [showKey, setShowKey] = useState(false);

  const [selectedModel, setSelectedModel] = useState(MODEL_PRESETS[0].value);
  const [customModel, setCustomModel] = useState('');
  const [baseUrl, setBaseUrl] = useState(MODEL_PRESETS[0].baseUrl);
  const [isCustomModel, setIsCustomModel] = useState(false);

  useEffect(() => {
    loadApiKeyStatus();
  }, [userId]);

  const loadApiKeyStatus = async () => {
    setIsLoading(true);
    try {
      const result = await userCenterService.getLLMConfig();
      setHasKey(result.has_key || false);
      setMaskedKey(result.masked_key || '');

      // 恢复模型配置
      const savedModel = result.model || '';
      const savedBaseUrl = result.base_url || '';
      if (savedModel) {
        const preset = MODEL_PRESETS.find(p => p.value === savedModel);
        if (preset && preset.value !== '__custom__') {
          setSelectedModel(preset.value);
          setBaseUrl(savedBaseUrl || preset.baseUrl);
          setIsCustomModel(false);
        } else {
          setSelectedModel('__custom__');
          setCustomModel(savedModel);
          setBaseUrl(savedBaseUrl);
          setIsCustomModel(true);
        }
      }
    } catch (error: any) {
      console.error('Failed to load API key status:', error);
      message.error('加载 API 配置失败');
    } finally {
      setIsLoading(false);
    }
  };

  const handleModelChange = (value: string) => {
    setSelectedModel(value);
    if (value === '__custom__') {
      setIsCustomModel(true);
    } else {
      setIsCustomModel(false);
      const preset = MODEL_PRESETS.find(p => p.value === value);
      if (preset) setBaseUrl(preset.baseUrl);
    }
  };

  const handleSaveApiKey = async () => {
    const trimmedKey = apiKey.trim();
    if (!trimmedKey) {
      message.warning('请输入 API Key');
      return;
    }

    const model = isCustomModel ? customModel.trim() : selectedModel;
    if (!model) {
      message.warning('请输入或选择模型名称');
      return;
    }

    setIsSaving(true);
    try {
      await userCenterService.saveLLMConfig(trimmedKey, model, baseUrl.trim());
      message.success('配置保存成功');
      setApiKey('');
      await loadApiKeyStatus();
    } catch (error: any) {
      console.error('Failed to save config:', error);
      message.error(error.message || '保存失败');
    } finally {
      setIsSaving(false);
    }
  };

  const handleClearApiKey = async () => {
    setIsSaving(true);
    try {
      await userCenterService.saveLLMConfig('');
      message.success('API Key 已清除');
      setHasKey(false);
      setMaskedKey('');
    } catch (error: any) {
      console.error('Failed to clear API key:', error);
      message.error(error.message || '清除失败');
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) {
    return (
      <div className="w-full pt-1">
        <div className="w-full rounded-xl border border-gray-200 bg-white p-8 flex items-center justify-center min-h-[200px]">
          <Spin />
        </div>
      </div>
    );
  }

  return (
    <div className="w-full pt-1 space-y-4">
      <div className="rounded-xl border border-gray-200 bg-white overflow-hidden">
        <div className="p-4 space-y-3">
          <div className="flex items-center gap-2.5">
            <div className="p-1.5 bg-indigo-100 rounded-md">
              <Key className="w-4 h-4 text-indigo-600" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-gray-800">AI 服务配置</h3>
              <p className="text-[11px] text-gray-500">配置 API Key、模型和接口地址，用于 AI-IDE 智能助手</p>
            </div>
          </div>

          <div className={`flex items-center gap-2 px-3 py-2 rounded-xl text-xs ${hasKey ? 'bg-green-50 text-green-700 border border-green-100' : 'bg-amber-50 text-amber-700 border border-amber-100'}`}>
            {hasKey ? <CheckCircle className="w-3.5 h-3.5 shrink-0" /> : <AlertCircle className="w-3.5 h-3.5 shrink-0" />}
            <span className="font-medium">{hasKey ? '已配置' : '未配置'}</span>
            {hasKey && maskedKey && (
              <span className="font-mono text-gray-500 bg-white/60 px-1.5 py-0.5 rounded">{maskedKey}</span>
            )}
            {hasKey && (
              <Button
                type="text"
                size="small"
                danger
                className="ml-auto !text-[11px] !px-2 !h-6"
                icon={<Trash2 className="w-3 h-3" />}
                onClick={handleClearApiKey}
                loading={isSaving}
              >
                清除
              </Button>
            )}
          </div>

          {/* 模型选择 */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-gray-600">模型</label>
            <Select
              value={selectedModel}
              onChange={handleModelChange}
              style={{ width: '100%' }}
              size="small"
              options={MODEL_PRESETS.map(p => ({ label: p.label, value: p.value }))}
            />
            {isCustomModel && (
              <Input
                size="small"
                value={customModel}
                onChange={(e) => setCustomModel(e.target.value)}
                placeholder="输入模型名称，如 gpt-4o、deepseek-chat"
                className="rounded-lg"
              />
            )}
          </div>

          {/* Base URL */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-gray-600">API 地址</label>
            <Input
              size="small"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder="https://api.openai.com/v1"
              className="rounded-lg"
            />
          </div>

          {/* API Key */}
          <div className="flex gap-2 items-center">
            <div className="relative flex-1">
              <Input
                type={showKey ? 'text' : 'password'}
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder={hasKey ? '输入新 Key 以更新' : 'sk-xxxxxxxxxxxxxxxx'}
                className="!pr-9 rounded-xl h-9"
                onPressEnter={handleSaveApiKey}
              />
              <button
                type="button"
                onClick={() => setShowKey(!showKey)}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 z-10"
              >
                {showKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
            <Button
              type="primary"
              icon={<Save className="w-4 h-4" />}
              onClick={handleSaveApiKey}
              loading={isSaving}
              disabled={!apiKey.trim()}
              className="rounded-xl h-9"
            >
              保存
            </Button>
          </div>

          <div className="text-[11px] text-gray-400 space-y-0.5 pt-1 border-t border-gray-100">
            <p>• API Key 安全存储在您的个人档案中，仅用于 AI-IDE 智能助手</p>
            <p>• 支持 OpenAI 兼容接口：DeepSeek、通义千问、SiliconFlow、OpenAI 等</p>
            <p>• 获取 Key：<a href="https://bailian.console.aliyun.com/" target="_blank" rel="noopener noreferrer" className="text-indigo-600 hover:underline">阿里云百炼</a> | <a href="https://platform.deepseek.com/" target="_blank" rel="noopener noreferrer" className="text-indigo-600 hover:underline">DeepSeek</a> | <a href="https://cloud.siliconflow.cn/" target="_blank" rel="noopener noreferrer" className="text-indigo-600 hover:underline">SiliconFlow</a></p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default OtherSettings;

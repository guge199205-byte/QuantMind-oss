/**
 * 环境检测弹窗组件
 * 用于检测系统环境、硬件配置和QMT客户端
 */
import React, { useState, useEffect } from 'react';
import {
  X,
  CheckCircle,
  XCircle,
  Loader2,
  Monitor,
  Cpu,
  HardDrive,
  Folder,
  AlertCircle,
  ChevronRight
} from 'lucide-react';
import axios from 'axios';
import { SERVICE_ENDPOINTS } from '../config/services';

interface EnvironmentCheckModalProps {
  isOpen: boolean;
  onClose: () => void;
  onComplete?: (config: any) => void;
}

interface DetectionResult {
  is_valid: boolean;
  message: string;
  [key: string]: any;
}

interface StepData {
  system?: DetectionResult;
  cpu?: DetectionResult;
  memory?: DetectionResult;
  qmt?: DetectionResult;
}

type Step = 'detection' | 'credentials' | 'testing' | 'complete';

export const EnvironmentCheckModal: React.FC<EnvironmentCheckModalProps> = ({
  isOpen,
  onClose,
  onComplete
}) => {
  const [step, setStep] = useState<Step>('detection');
  const [loading, setLoading] = useState(false);
  const [stepData, setStepData] = useState<StepData>({});
  const [credentials, setCredentials] = useState({
    accountId: '',
    password: ''
  });
  const [testResult, setTestResult] = useState<any>(null);

  // API基础URL
  const API_BASE = `${SERVICE_ENDPOINTS.TRADING}/environment`;

  useEffect(() => {
    if (isOpen && step === 'detection') {
      performDetection();
    }
  }, [isOpen, step]);

  // 执行环境检测
  const performDetection = async () => {
    setLoading(true);
    try {
      const response = await axios.get(`${API_BASE}/detect/all`);
      const data = response.data.data;

      setStepData({
        system: data.system,
        cpu: data.cpu,
        memory: data.memory,
        qmt: data.qmt
      });

      // 检查是否所有项都通过
      const allPassed = data.success;

      if (allPassed) {
        // 自动进入下一步
        setTimeout(() => {
          setStep('credentials');
        }, 1500);
      }
    } catch (error) {
      console.error('环境检测失败:', error);
    } finally {
      setLoading(false);
    }
  };

  // 测试QMT连接
  const testConnection = async () => {
    if (!credentials.accountId || !credentials.password) {
      alert('请输入资金账号和交易密码');
      return;
    }

    if (!stepData.qmt?.qmt_path) {
      alert('未检测到QMT路径');
      return;
    }

    setLoading(true);
    setStep('testing');

    try {
      const response = await axios.post(`${API_BASE}/test/qmt`, {
        qmt_path: stepData.qmt.qmt_path,
        account_id: credentials.accountId,
        password: credentials.password
      });

      setTestResult(response.data);

      if (response.data.success) {
        // 保存配置
        await saveConfig();
        setStep('complete');
      } else {
        alert(`连接测试失败: ${response.data.message}`);
        setStep('credentials');
      }
    } catch (error: any) {
      console.error('连接测试失败:', error);
      alert(`连接测试失败: ${error.response?.data?.detail || error.message}`);
      setStep('credentials');
    } finally {
      setLoading(false);
    }
  };

  // 保存配置
  const saveConfig = async () => {
    try {
      await axios.post(`${API_BASE}/config/save`, {
        user_id: 'default_user', // TODO: 使用实际用户ID
        qmt_path: stepData.qmt?.qmt_path,
        account_id: credentials.accountId,
        password: credentials.password
      });
    } catch (error) {
      console.error('保存配置失败:', error);
    }
  };

  // 完成并关闭
  const handleComplete = () => {
    if (onComplete && stepData.qmt) {
      onComplete({
        qmt_path: stepData.qmt.qmt_path,
        account_id: credentials.accountId
      });
    }
    onClose();
  };

  // 渲染检测项
  const renderDetectionItem = (
    icon: React.ReactNode,
    title: string,
    data?: DetectionResult
  ) => {
    if (!data) {
      return (
        <div className="flex items-center space-x-3 p-4 bg-gray-50 rounded-lg">
          {icon}
          <div className="flex-1">
            <div className="font-medium text-gray-700">{title}</div>
            <div className="text-sm text-gray-500">检测中...</div>
          </div>
          <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />
        </div>
      );
    }

    return (
      <div className={`flex items-center space-x-3 p-4 rounded-lg ${
        data.is_valid ? 'bg-green-50' : 'bg-red-50'
      }`}>
        {icon}
        <div className="flex-1">
          <div className="font-medium text-gray-700">{title}</div>
          <div className={`text-sm ${data.is_valid ? 'text-green-600' : 'text-red-600'}`}>
            {data.message}
          </div>
        </div>
        {data.is_valid ? (
          <CheckCircle className="w-5 h-5 text-green-500" />
        ) : (
          <XCircle className="w-5 h-5 text-red-500" />
        )}
      </div>
    );
  };

  // 渲染检测步骤
  const renderDetectionStep = () => (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-gray-800 mb-4">
        环境检测
      </h3>

      {renderDetectionItem(
        <Monitor className="w-6 h-6 text-blue-500" />,
        '系统环境',
        stepData.system
      )}

      {renderDetectionItem(
        <Cpu className="w-6 h-6 text-blue-500" />,
        'CPU配置',
        stepData.cpu
      )}

      {renderDetectionItem(
        <HardDrive className="w-6 h-6 text-blue-500" />,
        '内存配置',
        stepData.memory
      )}

      {renderDetectionItem(
        <Folder className="w-6 h-6 text-blue-500" />,
        'QMT客户端',
        stepData.qmt
      )}

      {stepData.system && !loading && (
        <div className="pt-4">
          {stepData.system.is_valid &&
           stepData.cpu?.is_valid &&
           stepData.memory?.is_valid &&
           stepData.qmt?.is_valid ? (
            <div className="text-center text-green-600">
              <CheckCircle className="w-12 h-12 mx-auto mb-2" />
              <p>所有检测项通过！</p>
            </div>
          ) : (
            <div className="text-center">
              <AlertCircle className="w-12 h-12 mx-auto mb-2 text-red-500" />
              <p className="text-red-600">部分检测项未通过</p>
              <button
                onClick={performDetection}
                className="mt-3 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
              >
                重新检测
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );

  // 渲染凭据输入步骤
  const renderCredentialsStep = () => (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-gray-800 mb-4">
        输入账户信息
      </h3>

      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <p className="text-sm text-blue-800">
          QMT客户端已检测到: <span className="font-mono">{stepData.qmt?.qmt_path}</span>
        </p>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          资金账号
        </label>
        <input
          type="text"
          value={credentials.accountId}
          onChange={(e) => setCredentials({ ...credentials, accountId: e.target.value })}
          className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="请输入资金账号"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          交易密码
        </label>
        <input
          type="password"
          value={credentials.password}
          onChange={(e) => setCredentials({ ...credentials, password: e.target.value })}
          className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="请输入交易密码"
        />
      </div>

      <div className="flex space-x-3 pt-4">
        <button
          onClick={() => setStep('detection')}
          className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50"
        >
          上一步
        </button>
        <button
          onClick={testConnection}
          disabled={!credentials.accountId || !credentials.password}
          className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed"
        >
          测试连接
        </button>
      </div>
    </div>
  );

  // 渲染测试步骤
  const renderTestingStep = () => (
    <div className="space-y-4 text-center py-8">
      <Loader2 className="w-16 h-16 mx-auto text-blue-500 animate-spin" />
      <h3 className="text-lg font-semibold text-gray-800">
        正在测试连接...
      </h3>
      <p className="text-gray-600">
        请稍候，正在验证账户信息
      </p>
    </div>
  );

  // 渲染完成步骤
  const renderCompleteStep = () => (
    <div className="space-y-4 text-center py-8">
      <CheckCircle className="w-16 h-16 mx-auto text-green-500" />
      <h3 className="text-lg font-semibold text-gray-800">
        配置完成！
      </h3>
      <p className="text-gray-600">
        QMT连接测试成功，配置已保存
      </p>

      {testResult?.account_info && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4 text-left">
          <p className="text-sm text-green-800">
            账号: {testResult.account_info.account_id}
          </p>
          <p className="text-sm text-green-800">
            总资产: ¥{testResult.account_info.total_asset?.toFixed(2) || 0}
          </p>
        </div>
      )}

      <button
        onClick={handleComplete}
        className="w-full px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700"
      >
        完成
      </button>
    </div>
  );

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        {/* 头部 */}
        <div className="flex items-center justify-between p-6 border-b">
          <h2 className="text-xl font-bold text-gray-800">环境检测</h2>
          <button
            onClick={onClose}
            className="p-1 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <X className="w-6 h-6 text-gray-500" />
          </button>
        </div>

        {/* 步骤指示器 */}
        <div className="flex items-center justify-center space-x-2 p-4 bg-gray-50">
          <div className={`flex items-center ${step === 'detection' ? 'text-blue-600' : 'text-gray-400'}`}>
            <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
              step === 'detection' ? 'bg-blue-600 text-white' : 'bg-gray-200'
            }`}>
              1
            </div>
            <span className="ml-2 text-sm font-medium">环境检测</span>
          </div>

          <ChevronRight className="w-5 h-5 text-gray-400" />

          <div className={`flex items-center ${step === 'credentials' || step === 'testing' || step === 'complete' ? 'text-blue-600' : 'text-gray-400'}`}>
            <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
              step === 'credentials' || step === 'testing' || step === 'complete' ? 'bg-blue-600 text-white' : 'bg-gray-200'
            }`}>
              2
            </div>
            <span className="ml-2 text-sm font-medium">账户配置</span>
          </div>

          <ChevronRight className="w-5 h-5 text-gray-400" />

          <div className={`flex items-center ${step === 'complete' ? 'text-blue-600' : 'text-gray-400'}`}>
            <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
              step === 'complete' ? 'bg-blue-600 text-white' : 'bg-gray-200'
            }`}>
              3
            </div>
            <span className="ml-2 text-sm font-medium">完成</span>
          </div>
        </div>

        {/* 内容 */}
        <div className="p-6">
          {step === 'detection' && renderDetectionStep()}
          {step === 'credentials' && renderCredentialsStep()}
          {step === 'testing' && renderTestingStep()}
          {step === 'complete' && renderCompleteStep()}
        </div>
      </div>
    </div>
  );
};

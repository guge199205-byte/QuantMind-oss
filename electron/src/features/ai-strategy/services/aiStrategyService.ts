/**
 * AI策略服务
 * 封装所有AI策略相关的API调用，支持MiniQMT语法
 */

import { BaseService } from '../../../shared/services/baseService';
import { SERVICE_URLS } from '../../../config/services';
import {
  AIStrategyGenerationParams,
  GenerationState,
  StrategyAnalysis,
  StrategyTemplate,
  StrategyExecution,
  StrategyExportConfig
} from '../types/strategy.types';
// MiniQMT support has been removed
// Using placeholder functions for compatibility

// Placeholder functions for miniqmtUtils
const validateMiniQMTCode = (code: string) => ({
  isValid: true,
  errors: [],
  warnings: [],
  suggestions: []
});

const formatMiniQMTCode = (code: string) => code;

const convertToMiniQMT = (code: string, params: any = {}) => code;

const extractMiniQMTParameters = (code: string) => ({});

const validateStockSymbols = (symbols: string[]) => ({
  valid: symbols,
  invalid: []
});

class AIStrategyService extends BaseService {
  constructor() {
    super('AIStrategyService', SERVICE_URLS.AI_STRATEGY);
  }

  /**
   * 枚举映射工具函数
   */
  private mapMarketType(marketType: string): string {
    const mapping: Record<string, string> = {
      'stock': 'CN',
      'futures': 'CN',
      'forex': 'GLOBAL',
      'crypto': 'GLOBAL'
    };
    return mapping[marketType] || 'CN';
  }

  private mapRiskPreference(riskPreference: string): string {
    const mapping: Record<string, string> = {
      'conservative': 'low',
      'moderate': 'medium',
      'aggressive': 'high'
    };
    return mapping[riskPreference] || 'medium';
  }

  private mapInvestmentStyle(investmentStyle: string): string {
    const mapping: Record<string, string> = {
      'value': 'conservative',
      'growth': 'aggressive',
      'balanced': 'balanced',
      'technical': 'custom'
    };
    return mapping[investmentStyle] || 'balanced';
  }

  private mapTimeframe(timeframe: string): string {
    const mapping: Record<string, string> = {
      'intraday': '1h',
      'daily': '1d',
      'weekly': '1w',
      'monthly': '1M'
    };
    return mapping[timeframe] || '1d';
  }

  private mapStrategyType(strategyType?: string): string {
    const mapping: Record<string, string> = {
      'trend_following': 'trend',
      'mean_reversion': 'mean_reversion',
      'arbitrage': 'arbitrage',
      'market_making': 'momentum'
    };
    return strategyType ? mapping[strategyType] || 'trend' : 'trend';
  }

  /**
   * 参数类型转换和验证
   */
  private validateAndConvertParams(params: AIStrategyGenerationParams): any {
    const converted: any = {
      description: params.description,
      market: this.mapMarketType(params.marketType),
      risk_level: this.mapRiskPreference(params.riskPreference),
      style: this.mapInvestmentStyle(params.investmentStyle),
      timeframe: this.mapTimeframe(params.timeframe),
      user_id: 'desktop-user'
    };

    // 数值类型参数转换和验证
    if (params.initialCapital && params.initialCapital > 0) {
      converted.initial_capital = parseFloat(params.initialCapital.toString());
    }

    if (params.maxPositions && params.maxPositions > 0) {
      converted.max_positions = parseInt(params.maxPositions.toString());
    }

    if (params.stopLoss && params.stopLoss > 0) {
      converted.stop_loss = parseFloat(params.stopLoss.toString());
    }

    if (params.takeProfit && params.takeProfit > 0) {
      converted.take_profit = parseFloat(params.takeProfit.toString());
    }

    // 高级参数处理
    if ((params as any).maxDrawdown && (params as any).maxDrawdown > 0 && (params as any).maxDrawdown <= 100) {
      converted.max_drawdown = parseFloat((params as any).maxDrawdown.toString());
    }

    if ((params as any).commissionRate && (params as any).commissionRate >= 0 && (params as any).commissionRate <= 1) {
      converted.commission_rate = parseFloat((params as any).commissionRate.toString());
    }

    if ((params as any).slippage && (params as any).slippage >= 0 && (params as any).slippage <= 1) {
      converted.slippage = parseFloat((params as any).slippage.toString());
    }

    // 股票池参数处理（新增）
    if (params.symbols && Array.isArray(params.symbols) && params.symbols.length > 0) {
      converted.symbols = params.symbols;
      this.logInfo('已添加股票池', { count: params.symbols.length, symbols: params.symbols });
    }

    // 策略类型和周期
    if (params.strategyType) {
      // 后端使用category字段
      converted.category = this.mapStrategyType(params.strategyType);
    }

    if (params.strategyLength) {
      converted.strategy_length = params.strategyLength;
    }

    if (params.backtestPeriod) {
      converted.backtest_period = params.backtestPeriod;
    }

    // 基准指数
    if (params.benchmark) {
      converted.benchmark = params.benchmark;
    }

    // 模板相关
    if (params.templateId) {
      converted.template_id = params.templateId;
    }

    if (params.useTemplate !== undefined) {
      converted.use_template = params.useTemplate;
    }

    // 数组参数处理
    if (params.examples && Array.isArray(params.examples)) {
      converted.examples = params.examples;
    }

    if (params.referenceStrategies && Array.isArray(params.referenceStrategies)) {
      // 后端不支持，暂时忽略
      this.logInfo('referenceStrategies parameter is not supported by backend', {
        strategies: params.referenceStrategies
      });
    }

    return converted;
  }

  /**
   * 生成AI策略（支持MiniQMT）
   */
  async generateStrategy(params: AIStrategyGenerationParams): Promise<GenerationState> {
    try {
      this.logInfo('开始生成AI策略', { params });

      // 验证股票代码格式
      if (params.symbols && params.symbols.length > 0) {
        const { valid, invalid } = validateStockSymbols(params.symbols);
        if (invalid.length > 0) {
          console.error('无效的股票代码', { invalid });
          return {
            status: 'error',
            progress: 0,
            message: `股票代码格式错误: ${invalid.join(', ')}`,
            error: `Invalid stock symbols: ${invalid.join(', ')}`
          };
        }
        params.symbols = valid;
      }

      // 使用参数验证和转换函数
      const convertedParams = this.validateAndConvertParams(params);

      // 添加MiniQMT相关参数
      convertedParams.output_format = 'miniqmt';
      convertedParams.include_imports = true;
      convertedParams.include_comments = true;

      this.logInfo('转换后的参数', { convertedParams });

      const response = await this.apiClient.post('/api/v1/strategy/generate', convertedParams);

      this.logInfo('AI策略生成成功', response.data);

      // 处理生成的策略代码
      const responseData = response.data as any;
      let strategyCode = responseData?.strategy_code || responseData?.code || '';
      if (strategyCode) {
        // 验证MiniQMT代码
        const validation = validateMiniQMTCode(strategyCode);
        if (!validation.isValid) {
          console.error('生成的代码不符合MiniQMT规范', { errors: validation.errors });
          return {
            status: 'error',
            progress: 100,
            message: '生成的代码不符合MiniQMT规范',
            error: validation.errors.join('; ')
          };
        }

        // 格式化代码
        strategyCode = formatMiniQMTCode(strategyCode);

        // 提取参数
        const extractedParams = extractMiniQMTParameters(strategyCode);

        // 更新响应数据
        responseData.strategy_code = strategyCode;
        responseData.extracted_parameters = extractedParams;
        responseData.validation_result = validation;
      }

      return {
        status: 'success',
        progress: 100,
        message: '策略生成成功',
        result: {
          ...(responseData || {}),
          strategy_code: strategyCode,
          framework: 'miniqmt'
        } as any,
      };
    } catch (error) {
      this.handleServiceError(error, 'generateStrategy');
    }
  }

  /**
   * 获取策略生成进度
   */
  async getGenerationProgress(taskId: string): Promise<GenerationState> {
    void taskId;
    throw new Error('进度轮询接口已下线，请改用 /api/v1/strategy/generate/stream (SSE)');
  }

  /**
   * 验证MiniQMT策略代码
   */
  async validateMiniQMTStrategy(code: string): Promise<{
    isValid: boolean;
    errors: string[];
    warnings: string[];
    suggestions: string[];
  }> {
    try {
      this.logInfo('验证MiniQMT策略代码');

      const validation = validateMiniQMTCode(code);

      this.logInfo('MiniQMT代码验证完成', {
        isValid: validation.isValid,
        errorsCount: validation.errors.length,
        warningsCount: validation.warnings.length
      });

      return validation;
    } catch (error) {
      console.error('MiniQMT代码验证失败', error);
      return {
        isValid: false,
        errors: ['代码验证失败'],
        warnings: [],
        suggestions: []
      };
    }
  }

  /**
   * 转换策略代码为MiniQMT格式
   */
  async convertToMiniQMTFormat(code: string, params: any = {}): Promise<{
    code: string;
    success: boolean;
    errors?: string[];
  }> {
    try {
      this.logInfo('转换策略代码为MiniQMT格式');

      const miniqmtCode = convertToMiniQMT(code, params);
      const formattedCode = formatMiniQMTCode(miniqmtCode);
      const validation = validateMiniQMTCode(formattedCode);

      if (!validation.isValid) {
        return {
          code: formattedCode,
          success: false,
          errors: validation.errors
        };
      }

      this.logInfo('代码转换成功');

      return {
        code: formattedCode,
        success: true
      };
    } catch (error) {
      console.error('代码转换失败', error);
      return {
        code: '',
        success: false,
        errors: ['代码转换失败']
      };
    }
  }

  /**
   * 格式化MiniQMT代码
   */
  formatMiniQMTCode(code: string): string {
    try {
      return formatMiniQMTCode(code);
    } catch (error) {
      console.error('代码格式化失败', error);
      return code;
    }
  }

  /**
   * 提取策略参数
   */
  extractStrategyParameters(code: string): Record<string, any> {
    try {
      return extractMiniQMTParameters(code);
    } catch (error) {
      console.error('参数提取失败', error);
      return {};
    }
  }

  /**
   * 生成策略模板
   */
  generateMiniQMTTemplate(templateId: string, parameters: Record<string, any>): string {
    try {
      // 导入模板生成函数
      const { generateMiniQMTCode } = require('../../../utils/miniqmt/miniqmtTemplates');
      return generateMiniQMTCode(templateId, parameters);
    } catch (error) {
      console.error('模板生成失败', error);
      return this.generateDefaultMiniQMTTemplate(parameters);
    }
  }

  /**
   * 生成默认MiniQMT模板
   */
  private generateDefaultMiniQMTTemplate(params: any): string {
    const universe = params.symbols && params.symbols.length > 0
      ? JSON.stringify(params.symbols)
      : '["000001.SZ", "600519.SH"]';

    return `from miniqmt import *
from miniqmt.indicators import *
from miniqmt.risk import *
import numpy as np
import pandas as pd

class DefaultStrategy(Strategy):
    """默认策略模板"""

    def __init__(self):
        super().__init__()
        self.universe = ${universe}
        self.initial_capital = ${params.initialCapital || 100000}
        self.max_positions = ${params.maxPositions || 5}
        self.stop_loss = ${params.stopLoss || 5}
        self.take_profit = ${params.takeProfit || 20}

    def initialize(self):
        """策略初始化"""
        self.log("策略初始化完成")
        self.log(f"股票池: {self.universe}")
        self.log(f"初始资金: {self.initial_capital}")

    def on_bar(self, bar):
        """K线数据更新时执行"""
        if bar.symbol not in self.universe:
            return

        # 获取当前持仓
        current_position = get_position(bar.symbol)

        # 获取历史数据
        df = get_bars(bar.symbol, '1d', 50)

        if len(df) < 20:
            return

        # 计算技术指标（示例：简单移动平均线）
        df['ma5'] = df['close'].rolling(5).mean()
        df['ma20'] = df['close'].rolling(20).mean()

        current_price = bar.close
        ma5 = df['ma5'].iloc[-1]
        ma20 = df['ma20'].iloc[-1]

        # 生成交易信号
        signal = self.generate_signal(current_price, ma5, ma20, current_position.volume)

        # 执行交易
        self.execute_trade(bar.symbol, signal, current_price, current_position.volume)

    def generate_signal(self, price, ma5, ma20, position_size):
        """生成交易信号"""
        # 金叉买入
        if ma5 > ma20 and position_size == 0:
            return 'BUY'

        # 死叉卖出
        elif ma5 < ma20 and position_size > 0:
            return 'SELL'

        # 止损
        elif position_size > 0:
            # 这里可以添加更复杂的止损逻辑
            pass

        return 'HOLD'

    def execute_trade(self, symbol, signal, price, current_position):
        """执行交易"""
        account_info = get_account_info()
        available_cash = account_info.available_cash

        if signal == 'BUY':
            # 计算买入数量
            amount = int(available_cash * 0.1 / price)
            if amount > 0:
                order_id = order_buy(symbol, amount, price=price)
                self.log(f"买入: {symbol} @ {price:.2f}, 数量: {amount}")

        elif signal == 'SELL' and current_position > 0:
            # 卖出所有持仓
            order_id = order_sell(symbol, current_position, price=price)
            self.log(f"卖出: {symbol} @ {price:.2f}, 数量: {current_position}")

    def on_order(self, order):
        """订单状态更新"""
        if order.status == 'filled':
            self.log(f"订单成交: {order.symbol} {order.side} {order.volume}@{order.price:.2f}")

    def on_error(self, error):
        """错误处理"""
        self.log(f"策略错误: {error}")

# 策略实例化
strategy = DefaultStrategy()
`;
  }

  /**
   * 验证股票代码
   */
  validateStockSymbols(symbols: string[]): { valid: string[]; invalid: string[] } {
    return validateStockSymbols(symbols);
  }

  /**
   * 保存策略
   */
  async saveStrategy(strategy: any): Promise<any> {
    try {
      this.logInfo('保存策略', { strategyId: strategy.id });

      const response = await this.apiClient.post('/api/v1/strategies', strategy);
      this.logInfo('策略保存成功', response.data);
      return response.data;
    } catch (error) {
      this.handleServiceError(error, 'saveStrategy');
    }
  }

  /**
   * 获取策略列表
   */
  async getStrategies(params?: {
    page?: number;
    pageSize?: number;
    status?: string;
    category?: string;
    search?: string;
  }): Promise<{ items: any[]; total: number }> {
    try {
      const response = await this.apiClient.get('/api/v1/strategies', params);
      return response.data as { items: any[]; total: number };
    } catch (error) {
      this.handleServiceError(error, 'getStrategies');
    }
  }

  /**
   * 获取策略详情
   */
  async getStrategy(id: string): Promise<any> {
    try {
      const response = await this.apiClient.get(`/api/v1/strategies/${id}`);
      return response.data;
    } catch (error) {
      this.handleServiceError(error, 'getStrategy');
    }
  }

  /**
   * 更新策略
   */
  async updateStrategy(id: string, updates: any): Promise<any> {
    try {
      const response = await this.apiClient.put(`/api/v1/strategies/${id}`, updates);
      return response.data;
    } catch (error) {
      this.handleServiceError(error, 'updateStrategy');
    }
  }

  /**
   * 删除策略
   */
  async deleteStrategy(id: string): Promise<void> {
    try {
      await this.apiClient.delete(`/api/v1/strategies/${id}`);
      this.logInfo('策略删除成功', { strategyId: id });
    } catch (error) {
      this.handleServiceError(error, 'deleteStrategy');
    }
  }

  /**
   * 复制策略
   */
  async duplicateStrategy(id: string, name?: string): Promise<any> {
    try {
      const response = await this.apiClient.post(`/api/v1/strategies/${id}/duplicate`, {
        name,
      });
      return response.data;
    } catch (error) {
      this.handleServiceError(error, 'duplicateStrategy');
    }
  }

  /**
   * 获取策略模板
   */
  async getStrategyTemplates(category?: string): Promise<StrategyTemplate[]> {
    try {
      const params = category ? { category } : {};
      const response = await this.apiClient.get('/api/v1/templates', params);
      return response.data as StrategyTemplate[];
    } catch (error) {
      this.handleServiceError(error, 'getStrategyTemplates');
    }
  }

  /**
   * 分析策略
   */
  async analyzeStrategy(strategyId: string, analysisType: string): Promise<StrategyAnalysis> {
    try {
      const response = await this.apiClient.post(`/api/v1/strategies/${strategyId}/analyze`, {
        analysis_type: analysisType,
      });
      return response.data as StrategyAnalysis;
    } catch (error) {
      this.handleServiceError(error, 'analyzeStrategy');
    }
  }

  /**
   * 执行策略
   */
  async executeStrategy(strategyId: string, params?: any): Promise<StrategyExecution> {
    try {
      const response = await this.apiClient.post(`/api/v1/strategies/${strategyId}/execute`, params);
      return response.data as StrategyExecution;
    } catch (error) {
      this.handleServiceError(error, 'executeStrategy');
    }
  }

  /**
   * 获取执行状态
   */
  async getExecutionStatus(executionId: string): Promise<StrategyExecution> {
    try {
      const response = await this.apiClient.get(`/api/v1/strategies/executions/${executionId}`);
      return response.data as StrategyExecution;
    } catch (error) {
      this.handleServiceError(error, 'getExecutionStatus');
    }
  }

  /**
   * 停止策略执行
   */
  async stopExecution(executionId: string): Promise<void> {
    try {
      await this.apiClient.post(`/api/v1/strategies/executions/${executionId}/stop`);
      this.logInfo('策略执行已停止', { executionId });
    } catch (error) {
      this.handleServiceError(error, 'stopExecution');
    }
  }

  /**
   * 导出策略
   */
  async exportStrategy(strategyId: string, config: StrategyExportConfig): Promise<string> {
    try {
      const response = await this.apiClient.post(`/api/v1/strategies/${strategyId}/export`, {
        format: config.format || 'json'
      });
      return (response.data as any).downloadUrl || (response.data as any).data;
    } catch (error) {
      this.handleServiceError(error, 'exportStrategy');
    }
  }

  /**
   * 导入策略
   */
  async importStrategy(file: File): Promise<any> {
    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await this.apiClient.post('/api/v1/strategies/import', formData, {
        'Content-Type': 'multipart/form-data',
      });
      return response.data;
    } catch (error) {
      this.handleServiceError(error, 'importStrategy');
    }
  }

  /**
   * 分享策略
   */
  async shareStrategy(strategyId: string, visibility: string, description: string): Promise<any> {
    try {
      const response = await this.apiClient.post(`/api/v1/strategies/${strategyId}/share`, {
        visibility,
        description,
      });
      return response.data;
    } catch (error) {
      this.handleServiceError(error, 'shareStrategy');
    }
  }

  /**
   * 获取策略统计信息
   */
  async getStrategyStats(): Promise<{
    total: number;
    active: number;
    draft: number;
    archived: number;
  }> {
    try {
      const response = await this.apiClient.get('/api/v1/strategies/stats');
      return response.data as {
        total: number;
        active: number;
        draft: number;
        archived: number;
      };
    } catch (error) {
      this.handleServiceError(error, 'getStrategyStats');
    }
  }
}

// 导出单例实例
export const aiStrategyService = new AIStrategyService();
export default aiStrategyService;

/**
 * 组件化代码生成器
 * 基于策略模板和组件系统生成完整的策略代码
 */

import {
  StrategyTemplate,
  StrategyComponent,
  ComponentType,
  GenerationStage,
  GeneratedComponent,
  StrategyGenerationRequest,
  StrategyGenerationResult,
  ComponentCodeTemplate
} from '../types/template';
import { StrategyParams } from '../types/strategy';
import { codeProcessor } from './codeProcessor';

// ==================== 组件代码模板库 ====================

// ComponentType 常量对象
const COMPONENT_TYPES = {
  DATA_HANDLING: 'DATA_HANDLING' as const,
  LOGIC: 'LOGIC' as const,
  RISK_CONTROL: 'RISK_CONTROL' as const,
  OPTIMIZATION: 'OPTIMIZATION' as const,
  ENTRY: 'ENTRY' as const,
  EXIT: 'EXIT' as const,
  RISK: 'RISK' as const,
};

const COMPONENT_CODE_TEMPLATES: Record<ComponentType, ComponentCodeTemplate[]> = {
  [COMPONENT_TYPES.DATA_HANDLING]: [
    {
      id: 'market_data_processor',
      name: '市场数据处理器',
      type: COMPONENT_TYPES.DATA_HANDLING,
      description: '基础市场数据获取和处理组件',
      codeTemplate: `
# 市场数据处理器
class MarketDataProcessor:
    def __init__(self, {{markets}}, {{dataSources}}, {{preprocessing}}):
        self.markets = markets
        self.data_sources = dataSources
        self.preprocessing = preprocessing
        self.data_cache = {}

    def fetch_data(self, symbol, start_date, end_date):
        """获取市场数据"""
        cache_key = f"{symbol}_{start_date}_{end_date}"
        if cache_key in self.data_cache:
            return self.data_cache[cache_key]

        try:
            # 获取原始数据
            raw_data = self._fetch_raw_data(symbol, start_date, end_date)

            if self.preprocessing:
                data = self._preprocess_data(raw_data)
            else:
                data = raw_data

            self.data_cache[cache_key] = data
            return data

        except Exception as e:
            raise Exception(f"获取数据失败 {symbol}: {str(e)}")

    def _fetch_raw_data(self, symbol, start_date, end_date):
        """获取原始数据"""
        # 实现具体的数据获取逻辑
        pass

    def _preprocess_data(self, data):
        """数据预处理"""
        # 数据清洗和处理
        data = data.dropna()

        # 异常值处理
        for col in ['open', 'high', 'low', 'close', 'volume']:
            if col in data.columns:
                data[col] = data[col].clip(lower=data[col].quantile(0.01),
                                          upper=data[col].quantile(0.99))

        return data
`,
      placeholders: [
        { name: 'markets', description: '支持的市场', type: 'array', required: true },
        { name: 'dataSources', description: '数据源', type: 'array', required: true },
        { name: 'preprocessing', description: '是否预处理', type: 'boolean', required: false, defaultValue: true }
      ],
      parameters: [
        { name: 'markets', type: 'string[]', description: '支持的市场', required: true },
        { name: 'dataSources', type: 'string[]', description: '数据源', required: true },
        { name: 'preprocessing', type: 'boolean', description: '是否预处理', required: false }
      ],
      requiredParams: ['markets', 'dataSources'],
      optionalParams: ['preprocessing'],
      imports: ['pandas', 'numpy', 'yfinance', 'datetime']
    }
  ],

  [COMPONENT_TYPES.LOGIC]: [
    {
      id: 'dual_ma_backtester',
      name: '双均线回测逻辑',
      type: COMPONENT_TYPES.LOGIC,
      description: '双均线交叉策略的核心交易逻辑',
      codeTemplate: `
# 双均线策略核心逻辑
class DualMAStrategy:
    def __init__(self, {{fastPeriod}}, {{slowPeriod}}, {{signalMethod}}):
        self.fast_period = fastPeriod
        self.slow_period = slowPeriod
        self.signal_method = signalMethod
        self.position = 0
        self.signals = []

    def generate_signals(self, data):
        """生成交易信号"""
        # 计算移动平均线
        data['fast_ma'] = data['close'].rolling(window=self.fast_period).mean()
        data['slow_ma'] = data['close'].rolling(window=self.slow_period).mean()

        # 生成信号
        if self.signal_method == 'crossover':
            data['signal'] = 0
            data.loc[data['fast_ma'] > data['slow_ma'], 'signal'] = 1
            data.loc[data['fast_ma'] < data['slow_ma'], 'signal'] = -1

            # 检测交叉点
            data['signal_change'] = data['signal'].diff()
            data['buy_signal'] = (data['signal_change'] == 2) | ((data['signal'] == 1) & (data['signal'].shift(1) == -1))
            data['sell_signal'] = (data['signal_change'] == -2) | ((data['signal'] == -1) & (data['signal'].shift(1) == 1))

        return data

    def execute_trade(self, signal, price, date):
        """执行交易"""
        if signal == 1 and self.position <= 0:  # 买入信号
            self.position = 1
            return {'action': 'buy', 'price': price, 'date': date, 'quantity': 1}
        elif signal == -1 and self.position >= 0:  # 卖出信号
            self.position = -1
            return {'action': 'sell', 'price': price, 'date': date, 'quantity': 1}

        return None
`,
      placeholders: [
        { name: 'fastPeriod', description: '快线周期', type: 'number', required: true },
        { name: 'slowPeriod', description: '慢线周期', type: 'number', required: true },
        { name: 'signalMethod', description: '信号方法', type: 'string', required: true }
      ],
      parameters: [
        { name: 'fastPeriod', type: 'number', description: '快线周期', required: true },
        { name: 'slowPeriod', type: 'number', description: '慢线周期', required: true },
        { name: 'signalMethod', type: 'string', description: '信号方法', required: true }
      ],
      requiredParams: ['fastPeriod', 'slowPeriod', 'signalMethod'],
      optionalParams: [],
      imports: ['pandas', 'numpy', 'talib']
    },
    {
      id: 'macd_backtester',
      name: 'MACD策略逻辑',
      type: COMPONENT_TYPES.LOGIC,
      description: 'MACD指标策略的核心交易逻辑',
      codeTemplate: `
# MACD策略核心逻辑
class MACDStrategy:
    def __init__(self, {{fastPeriod}}, {{slowPeriod}}, {{signalPeriod}}, {{signalMethod}}):
        self.fast_period = fastPeriod
        self.slow_period = slowPeriod
        self.signal_period = signalPeriod
        self.signal_method = signalMethod
        self.position = 0

    def calculate_indicators(self, data):
        """计算MACD指标"""
        # 使用talib计算MACD
        data['macd'], data['signal'], data['hist'] = talib.MACD(
            data['close'].values,
            fastperiod=self.fast_period,
            slowperiod=self.slow_period,
            signalperiod=self.signal_period
        )

        return data

    def generate_signals(self, data):
        """生成交易信号"""
        data = self.calculate_indicators(data)

        if self.signal_method == 'crossover':
            # MACD线上穿信号线
            data['buy_signal'] = (data['macd'] > data['signal']) & (data['macd'].shift(1) <= data['signal'].shift(1))
            # MACD线下穿信号线
            data['sell_signal'] = (data['macd'] < data['signal']) & (data['macd'].shift(1) >= data['signal'].shift(1))

        return data

    def execute_trade(self, row):
        """执行交易"""
        if row['buy_signal'] and self.position <= 0:
            self.position = 1
            return {'action': 'buy', 'price': row['close'], 'date': row.name, 'quantity': 1}
        elif row['sell_signal'] and self.position >= 0:
            self.position = -1
            return {'action': 'sell', 'price': row['close'], 'date': row.name, 'quantity': 1}

        return None
`,
      placeholders: [
        { name: 'fastPeriod', description: '快线周期', type: 'number', required: true },
        { name: 'slowPeriod', description: '慢线周期', type: 'number', required: true },
        { name: 'signalPeriod', description: '信号线周期', type: 'number', required: true },
        { name: 'signalMethod', description: '信号方法', type: 'string', required: true }
      ],
      parameters: [
        { name: 'fastPeriod', type: 'number', description: '快线周期', required: true },
        { name: 'slowPeriod', type: 'number', description: '慢线周期', required: true },
        { name: 'signalPeriod', type: 'number', description: '信号线周期', required: true },
        { name: 'signalMethod', type: 'string', description: '信号方法', required: true }
      ],
      requiredParams: ['fastPeriod', 'slowPeriod', 'signalPeriod', 'signalMethod'],
      optionalParams: [],
      imports: ['pandas', 'numpy', 'talib']
    }
  ],

  [COMPONENT_TYPES.RISK_CONTROL]: [
    {
      id: 'basic_risk_manager',
      name: '基础风险管理器',
      type: COMPONENT_TYPES.RISK_CONTROL,
      description: '提供基础的止损、止盈和仓位管理功能',
      codeTemplate: `
# 基础风险管理器
class RiskManager:
    def __init__(self, {{stopLoss}}, {{takeProfit}}, {{maxDrawdown}}, {{positionSize}}):
        self.stop_loss = stopLoss
        self.take_profit = takeProfit
        self.max_drawdown = maxDrawdown
        self.position_size = positionSize
        self.initial_capital = None
        self.peak_capital = None
        self.current_drawdown = 0

    def set_initial_capital(self, capital):
        """设置初始资金"""
        self.initial_capital = capital
        self.peak_capital = capital

    def calculate_position_size(self, current_capital, price):
        """计算仓位大小"""
        risk_amount = current_capital * (self.position_size / 100)
        position_value = min(risk_amount, current_capital * 0.95)  # 最多95%仓位
        return position_value / price

    def check_stop_loss(self, entry_price, current_price, position_type):
        """检查止损条件"""
        if position_type == 'long':
            loss_pct = (entry_price - current_price) / entry_price * 100
            return loss_pct >= self.stop_loss
        else:  # short
            loss_pct = (current_price - entry_price) / entry_price * 100
            return loss_pct >= self.stop_loss

    def check_take_profit(self, entry_price, current_price, position_type):
        """检查止盈条件"""
        if position_type == 'long':
            profit_pct = (current_price - entry_price) / entry_price * 100
            return profit_pct >= self.take_profit
        else:  # short
            profit_pct = (entry_price - current_price) / entry_price * 100
            return profit_pct >= self.take_profit

    def update_drawdown(self, current_capital):
        """更新回撤"""
        if current_capital > self.peak_capital:
            self.peak_capital = current_capital

        self.current_drawdown = (self.peak_capital - current_capital) / self.peak_capital * 100
        return self.current_drawdown

    def should_stop_trading(self):
        """判断是否应该停止交易"""
        return self.current_drawdown >= self.max_drawdown

    def validate_trade(self, current_capital, entry_price, position_type):
        """验证交易是否合规"""
        # 检查回撤限制
        if self.should_stop_trading():
            return False, "超过最大回撤限制"

        # 检查仓位大小
        position_value = self.calculate_position_size(current_capital, entry_price) * entry_price
        if position_value > current_capital * 0.95:
            return False, "仓位过大"

        return True, "交易合规"
`,
      placeholders: [
        { name: 'stopLoss', description: '止损百分比', type: 'number', required: true },
        { name: 'takeProfit', description: '止盈百分比', type: 'number', required: true },
        { name: 'maxDrawdown', description: '最大回撤', type: 'number', required: true },
        { name: 'positionSize', description: '仓位大小', type: 'number', required: true }
      ],
      parameters: [
        { name: 'stopLoss', type: 'number', description: '止损百分比', required: true },
        { name: 'takeProfit', type: 'number', description: '止盈百分比', required: true },
        { name: 'maxDrawdown', type: 'number', description: '最大回撤', required: true },
        { name: 'positionSize', type: 'number', description: '仓位大小', required: true }
      ],
      requiredParams: ['stopLoss', 'takeProfit', 'maxDrawdown', 'positionSize'],
      optionalParams: [],
      imports: ['pandas', 'numpy']
    }
  ],

  [COMPONENT_TYPES.OPTIMIZATION]: [
    {
      id: 'performance_analyzer',
      name: '性能分析器',
      type: COMPONENT_TYPES.OPTIMIZATION,
      description: '策略性能分析和指标计算组件',
      codeTemplate: `
# 性能分析器
class PerformanceAnalyzer:
    def __init__(self, {{enableMetrics}}, {{benchmark}}):
        self.enable_metrics = enableMetrics
        self.benchmark = benchmark

    def calculate_performance_metrics(self, returns, benchmark_returns=None):
        """计算性能指标"""
        if not self.enable_metrics:
            return {}

        metrics = {}

        # 基础收益指标
        metrics['total_return'] = (returns + 1).prod() - 1
        metrics['annual_return'] = (returns + 1).prod() ** (252 / len(returns)) - 1
        metrics['volatility'] = returns.std() * np.sqrt(252)

        # 夏普比率
        risk_free_rate = 0.03 / 252  # 假设3%年化无风险利率
        excess_returns = returns - risk_free_rate
        metrics['sharpe_ratio'] = excess_returns.mean() / excess_returns.std() * np.sqrt(252)

        # 最大回撤
        cumulative_returns = (returns + 1).cumprod()
        running_max = cumulative_returns.expanding().max()
        drawdown = (cumulative_returns - running_max) / running_max
        metrics['max_drawdown'] = drawdown.min()

        # 胜率
        metrics['win_rate'] = (returns > 0).mean()

        # 盈亏比
        positive_returns = returns[returns > 0]
        negative_returns = returns[returns < 0]
        if len(negative_returns) > 0:
            metrics['profit_loss_ratio'] = positive_returns.mean() / abs(negative_returns.mean())
        else:
            metrics['profit_loss_ratio'] = float('inf')

        # 相对基准指标
        if benchmark_returns is not None:
            metrics['alpha'] = self._calculate_alpha(returns, benchmark_returns)
            metrics['beta'] = self._calculate_beta(returns, benchmark_returns)
            metrics['information_ratio'] = self._calculate_information_ratio(returns, benchmark_returns)

        return metrics

    def _calculate_alpha(self, returns, benchmark_returns):
        """计算Alpha"""
        risk_free_rate = 0.03 / 252
        beta = self._calculate_beta(returns, benchmark_returns)
        benchmark_return = (benchmark_returns + 1).prod() ** (252 / len(benchmark_returns)) - 1
        strategy_return = (returns + 1).prod() ** (252 / len(returns)) - 1

        alpha = strategy_return - (risk_free_rate + beta * (benchmark_return - risk_free_rate))
        return alpha

    def _calculate_beta(self, returns, benchmark_returns):
        """计算Beta"""
        if len(returns) != len(benchmark_returns):
            return np.nan

        covariance = np.cov(returns, benchmark_returns)[0, 1]
        benchmark_variance = np.var(benchmark_returns)

        return covariance / benchmark_variance if benchmark_variance != 0 else 0

    def _calculate_information_ratio(self, returns, benchmark_returns):
        """计算信息比率"""
        active_returns = returns - benchmark_returns
        if active_returns.std() == 0:
            return 0

        return active_returns.mean() / active_returns.std() * np.sqrt(252)

    def generate_performance_report(self, metrics):
        """生成性能报告"""
        if not metrics:
            return "性能分析未启用"

        report = f"""
=== 策略性能报告 ===

收益指标:
- 总收益率: {metrics.get('total_return', 0):.2%}
- 年化收益率: {metrics.get('annual_return', 0):.2%}
- 年化波动率: {metrics.get('volatility', 0):.2%}

风险指标:
- 夏普比率: {metrics.get('sharpe_ratio', 0):.2f}
- 最大回撤: {metrics.get('max_drawdown', 0):.2%}
- 投资胜率: {metrics.get('win_rate', 0):.2%}
- 盈亏比: {metrics.get('profit_loss_ratio', 0):.2f}

基准相关指标:
- Alpha: {metrics.get('alpha', 0):.2%}
"""
        return report
`,
      placeholders: [
        { name: 'enableMetrics', description: '是否启用指标计算', type: 'boolean', required: true },
        { name: 'benchmark', description: '基准指数', type: 'string', required: false }
      ],
      parameters: [
        { name: 'enableMetrics', type: 'boolean', description: '是否启用指标计算', required: true },
        { name: 'benchmark', type: 'string', description: '基准指数', required: false }
      ],
      requiredParams: ['enableMetrics'],
      optionalParams: ['benchmark'],
      imports: ['pandas', 'numpy', 'scipy']
    }
  ],

  // 新增组件类型的空模板
  [COMPONENT_TYPES.ENTRY]: [],
  [COMPONENT_TYPES.EXIT]: [],
  [COMPONENT_TYPES.RISK]: []
};

// ==================== 代码生成阶段定义 ====================

const GENERATION_STAGES: GenerationStage[] = [
  {
    name: 'framework',
    type: 'framework',
    order: 1,
    required: true,
    dependencies: []
  },
  {
    name: 'imports',
    type: 'imports',
    order: 2,
    required: true,
    dependencies: ['framework']
  },
  {
    name: 'data_handling',
    type: 'data_handling',
    order: 3,
    required: true,
    dependencies: ['imports']
  },
  {
    name: 'logic',
    type: 'logic',
    order: 4,
    required: true,
    dependencies: ['data_handling']
  },
  {
    name: 'risk_control',
    type: 'risk_control',
    order: 5,
    required: true,
    dependencies: ['logic']
  },
  {
    name: 'optimization',
    type: 'optimization',
    order: 6,
    required: false,
    dependencies: ['risk_control']
  }
];

// ==================== 主代码生成器 ====================

export class ComponentCodeGenerator {
  private stages: GenerationStage[];

  constructor() {
    this.stages = [...GENERATION_STAGES];
  }

  /**
   * 生成策略代码
   */
  async generateStrategy(request: StrategyGenerationRequest): Promise<StrategyGenerationResult> {
    const startTime = Date.now();
    const errors: string[] = [];
    const warnings: string[] = [];
    const suggestions: string[] = [];

    try {
      // 1. 验证生成请求
      const validationResult = this.validateGenerationRequest(request);
      if (!validationResult.isValid) {
        errors.push(...validationResult.errors);
        return {
          success: false,
          errors,
          warnings,
          suggestions
        };
      }

      // 2. 分阶段生成代码
      const generatedCode = await this.generateByStages(request, warnings);

      // 3. 后处理和优化
      const processedCode = await this.postProcessCode(generatedCode, request, suggestions);

      // 4. 验证生成的代码
      const validationResults = await this.validateGeneratedCode(processedCode);

      // 5. 生成组件信息
      const generatedComponents = this.extractComponents(request.template, request.userParams);

      const generationTime = Date.now() - startTime;

      return {
        success: validationResults.isValid,
        template: request.template,
        strategy: {
          code: processedCode,
          parameters: this.mergeParameters(request.userParams, request.template?.defaultParameters),
          components: generatedComponents,
          metadata: {
            generationTime,
            templateId: request.template?.id || 'custom',
            customizations: this.getCustomizations(request, generatedComponents)
          }
        },
        errors: validationResults.errors,
        warnings: [...warnings, ...validationResults.warnings],
        suggestions
      };

    } catch (error) {
      errors.push(`代码生成失败: ${error instanceof Error ? error.message : '未知错误'}`);
      return {
        success: false,
        errors,
        warnings,
        suggestions
      };
    }
  }

  /**
   * 验证生成请求
   */
  private validateGenerationRequest(request: StrategyGenerationRequest): { isValid: boolean; errors: string[] } {
    const errors: string[] = [];

    if (!request.userParams) {
      errors.push('缺少用户参数');
    }

    if (!request.template && !request.customComponents) {
      errors.push('必须提供策略模板或自定义组件');
    }

    if (request.template) {
      // 验证模板参数
      for (const [key, value] of Object.entries(request.template.defaultParameters)) {
        if (request.template.validationRules) {
          const rule = request.template.validationRules.find(r => r.field === key);
          if (rule && !this.validateParameter(value, rule.type)) {
            errors.push(`参数 ${key} 不符合规则: 类型验证失败`);
          }
        }
      }
    }

    return {
      isValid: errors.length === 0,
      errors
    };
  }

  /**
   * 分阶段生成代码
   */
  private async generateByStages(
    request: StrategyGenerationRequest,
    warnings: string[]
  ): Promise<string> {
    const codeSections: string[] = [];

    // 按顺序执行每个生成阶段
    for (const stage of this.stages) {
      try {
        const sectionCode = await this.generateStage(stage, request, warnings);
        if (sectionCode) {
          codeSections.push(`# === ${stage.name.toUpperCase()} ===\n${sectionCode}\n`);
        }
      } catch (error) {
        if (stage.required) {
          throw error;
        } else {
          warnings.push(`阶段 ${stage.name} 生成失败: ${error}`);
        }
      }
    }

    return codeSections.join('\n');
  }

  /**
   * 生成单个阶段的代码
   */
  private async generateStage(
    stage: GenerationStage,
    request: StrategyGenerationRequest,
    warnings: string[]
  ): Promise<string> {
    switch (stage.type) {
      case 'framework':
        return this.generateFramework(request);

      case 'imports':
        return this.generateImports(request);

      case 'data_handling':
        return this.generateDataHandling(request);

      case 'logic':
        return this.generateLogic(request);

      case 'risk_control':
        return this.generateRiskControl(request);

      case 'optimization':
        return this.generateOptimization(request);

      default:
        warnings.push(`未知的阶段类型: ${stage.type}`);
        return '';
    }
  }

  /**
   * 生成框架代码
   */
  private generateFramework(request: StrategyGenerationRequest): string {
    const template = request.template;
    const params = request.userParams;

    return `"""
${template?.name || '自定义量化策略'}
${template?.description || '基于组件化生成的量化交易策略'}

策略参数:
${JSON.stringify(params, null, 2)}

生成时间: ${new Date().toISOString()}
模板版本: ${template?.version || 'custom'}
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

class QuantStrategy:
    def __init__(self):
        """初始化策略"""
        self.name = "${template?.name || 'Custom Strategy'}"
        self.params = ${JSON.stringify(params, null, 8)}
        self.data_processor = None
        self.strategy_logic = None
        self.risk_manager = None
        self.performance_analyzer = None

        # 交易状态
        self.position = 0
        self.trades = []
        self.current_capital = self.params.get('initialCapital', 100000)
        self.initial_capital = self.current_capital

        # 初始化组件
        self._initialize_components()

    def _initialize_components(self):
        """初始化策略组件"""
        pass

    def run_backtest(self, data):
        """运行回测"""
        pass

    def generate_report(self):
        """生成报告"""
        pass
`;
  }

  /**
   * 生成导入语句
   */
  private generateImports(request: StrategyGenerationRequest): string {
    const allImports = new Set<string>();

    // 收集所有组件需要的导入
    if (request.template) {
      request.template.requiredComponents.forEach(component => {
        const templates = COMPONENT_CODE_TEMPLATES[component.type];
        if (templates) {
          templates.forEach(template => {
            template.imports.forEach(imp => allImports.add(imp));
          });
        }
      });
    }

    if (request.customComponents) {
      request.customComponents.forEach(component => {
        const templates = COMPONENT_CODE_TEMPLATES[component.type];
        if (templates) {
          templates.forEach(template => {
            template.imports.forEach(imp => allImports.add(imp));
          });
        }
      });
    }

    // 添加基础导入
    allImports.add('pandas');
    allImports.add('numpy');
    allImports.add('datetime');

    const importStatements = Array.from(allImports).map(imp => {
      if (imp.includes('.')) {
        return `from ${imp} import *`;
      } else {
        return `import ${imp}`;
      }
    });

    return importStatements.join('\n');
  }

  /**
   * 生成数据处理组件
   */
  private generateDataHandling(request: StrategyGenerationRequest): string {
    const component = this.findComponent(request, COMPONENT_TYPES.DATA_HANDLING);
    if (!component) return '';

    const template = COMPONENT_CODE_TEMPLATES[COMPONENT_TYPES.DATA_HANDLING][0];
    return this.fillTemplate(template, component.parameters);
  }

  /**
   * 生成策略逻辑组件
   */
  private generateLogic(request: StrategyGenerationRequest): string {
    const component = this.findComponent(request, COMPONENT_TYPES.LOGIC);
    if (!component) return '';

    // 根据策略类型选择合适的模板
    const templates = COMPONENT_CODE_TEMPLATES[COMPONENT_TYPES.LOGIC];
    let selectedTemplate = templates[0];

    if (request.template?.id === 'dual_ma_crossover') {
      selectedTemplate = templates.find(t => t.id === 'dual_ma_backtester') || templates[0];
    } else if (request.template?.id === 'macd_strategy') {
      selectedTemplate = templates.find(t => t.id === 'macd_backtester') || templates[0];
    }

    return this.fillTemplate(selectedTemplate, component.parameters);
  }

  /**
   * 生成风险控制组件
   */
  private generateRiskControl(request: StrategyGenerationRequest): string {
    const component = this.findComponent(request, COMPONENT_TYPES.RISK_CONTROL);
    if (!component) return '';

    const template = COMPONENT_CODE_TEMPLATES[COMPONENT_TYPES.RISK_CONTROL][0];
    return this.fillTemplate(template, component.parameters);
  }

  /**
   * 生成优化组件
   */
  private generateOptimization(request: StrategyGenerationRequest): string {
    const component = this.findComponent(request, COMPONENT_TYPES.OPTIMIZATION);
    if (!component) return '';

    const template = COMPONENT_CODE_TEMPLATES[COMPONENT_TYPES.OPTIMIZATION][0];
    return this.fillTemplate(template, component.parameters);
  }

  /**
   * 填充模板占位符
   */
  private fillTemplate(template: ComponentCodeTemplate, parameters: Record<string, any>): string {
    let code = template.codeTemplate;

    // 替换占位符
    template.placeholders.forEach(placeholder => {
      const value = parameters[placeholder.name] ?? placeholder.defaultValue;
      if (value !== undefined) {
        const placeholderPattern = new RegExp(`{{${placeholder.name}}}`, 'g');
        code = code.replace(placeholderPattern, this.formatValue(value, placeholder.type));
      }
    });

    return code;
  }

  /**
   * 格式化值
   */
  private formatValue(value: any, type: string): string {
    switch (type) {
      case 'string':
        return `"${value}"`;
      case 'number':
        return value.toString();
      case 'boolean':
        return value ? 'True' : 'False';
      case 'array':
        return Array.isArray(value) ? `[${value.map(v => `"${v}"`).join(', ')}]` : '[]';
      case 'object':
        return typeof value === 'object' ? JSON.stringify(value) : '{}';
      default:
        return String(value);
    }
  }

  /**
   * 查找组件
   */
  private findComponent(request: StrategyGenerationRequest, componentType: ComponentType): StrategyComponent | null {
    // 优先从模板中查找
    if (request.template) {
      const component = request.template.requiredComponents.find(c => c.type === componentType);
      if (component) return component;
    }

    // 从自定义组件中查找
    if (request.customComponents) {
      const component = request.customComponents.find(c => c.type === componentType);
      if (component) return component;
    }

    return null;
  }

  /**
   * 后处理代码
   */
  private async postProcessCode(
    code: string,
    request: StrategyGenerationRequest,
    suggestions: string[]
  ): Promise<string> {
    let processedCode = code;

    // 1. 代码格式化
    if (request.generationConfig.includeComments) {
      processedCode = this.addComments(processedCode, request);
    }

    // 2. 错误处理
    if (request.generationConfig.includeErrorHandling) {
      processedCode = this.addErrorHandling(processedCode);
    }

    // 3. 性能优化
    if (request.generationConfig.includePerformanceOptimization) {
      processedCode = this.addPerformanceOptimizations(processedCode, suggestions);
    }

    // 4. 日志记录
    if (request.generationConfig.includeLogging) {
      processedCode = this.addLogging(processedCode);
    }

    return processedCode;
  }

  /**
   * 添加注释
   */
  private addComments(code: string, request: StrategyGenerationRequest): string {
    // 添加策略说明注释
    const header = `"""
策略说明:
- 策略类型: ${request.template?.category || '自定义'}
- 适用市场: ${request.userParams.market || '通用'}
- 时间框架: ${request.userParams.timeframe || '任意'}
- 风险等级: ${request.userParams.riskLevel || '中等'}

生成参数:
${JSON.stringify(request.userParams, null, 2)}
"""
`;

    return header + code;
  }

  /**
   * 添加错误处理
   */
  private addErrorHandling(code: string): string {
    // 在关键函数中添加try-catch块
    return code.replace(
      /def (fetch_data|generate_signals|execute_trade)\(self.*?\):/g,
      'def $1(self$2):\n        try:'
    );
  }

  /**
   * 添加性能优化
   */
  private addPerformanceOptimizations(code: string, suggestions: string[]): string {
    suggestions.push('考虑使用向量化操作提升性能');
    suggestions.push('可以使用缓存机制减少重复计算');

    return code;
  }

  /**
   * 添加日志记录
   */
  private addLogging(code: string): string {
    const loggingCode = `
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
`;

    return loggingCode + code.replace(/print\(/g, 'logger.info(');
  }

  /**
   * 验证生成的代码
   */
  private async validateGeneratedCode(code: string): Promise<{ isValid: boolean; errors: string[]; warnings: string[] }> {
    const errors: string[] = [];
    const warnings: string[] = [];

    try {
      // 使用代码处理器验证
      const validation = await codeProcessor.realTimeValidator.validate(code, []);

      if (!validation.isValid) {
        errors.push(...validation.errors.map(e => `${e}`));
      }

      warnings.push(...validation.warnings.map(w => `${w}`));

    } catch (error) {
      errors.push(`代码验证失败: ${error instanceof Error ? error.message : '未知错误'}`);
    }

    return {
      isValid: errors.length === 0,
      errors,
      warnings
    };
  }

  /**
   * 提取组件信息
   */
  private extractComponents(template?: StrategyTemplate, _params?: StrategyParams): GeneratedComponent[] {
    const components: GeneratedComponent[] = [];

    if (template) {
      template.requiredComponents.forEach(component => {
        components.push({
          type: component.type,
          name: component.name,
          code: `// ${component.name} component code`,
          parameters: component.parameters,
          validation: {
            isValid: true,
            errors: [],
            warnings: []
          }
        });
      });
    }

    return components;
  }

  /**
   * 合并参数
   */
  private mergeParameters(userParams: StrategyParams, templateParams?: Partial<StrategyParams>): StrategyParams {
    return { ...templateParams, ...userParams };
  }

  /**
   * 获取定制化信息
   */
  private getCustomizations(request: StrategyGenerationRequest, _components: GeneratedComponent[]): string[] {
    const customizations: string[] = [];

    if (request.template) {
      customizations.push(`使用模板: ${request.template.name}`);
    }

    if (request.customComponents && request.customComponents.length > 0) {
      customizations.push(`自定义组件: ${request.customComponents.map(c => c.name).join(', ')}`);
    }

    return customizations;
  }

  /**
   * 验证参数
   */
  private validateParameter(value: any, rule: string): boolean {
    // 简单的参数验证实现
    const rules = rule.split('|');

    for (const r of rules) {
      if (r === 'required' && !value) return false;
      if (r.startsWith('min:') && Number(value) < Number(r.split(':')[1])) return false;
      if (r.startsWith('max:') && Number(value) > Number(r.split(':')[1])) return false;
    }

    return true;
  }
}

// ==================== 导出 ====================

export const componentCodeGenerator = new ComponentCodeGenerator();
export { COMPONENT_CODE_TEMPLATES, GENERATION_STAGES };

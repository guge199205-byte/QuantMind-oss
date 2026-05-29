/**
 * 类型转换工具函数
 * 用于处理不同类型间的转换
 */

import type {
  Strategy,
  StrategyTemplate,
  StrategyCategory,
  StrategyMetadata
} from '../types/strategy';
import type {
  AIStrategy,
  AIStrategyParams,
  AIStrategyChatMessage,
  AIStrategyTemplate
} from '../types';

// 类型转换函数
export const convertAIStrategyToStrategy = (aiStrategy: AIStrategy): Strategy => {
  return {
    id: aiStrategy.id,
    name: aiStrategy.name,
    description: aiStrategy.description,
    code: aiStrategy.code,
    parameters: {
      description: aiStrategy.parameters.description,
      market: aiStrategy.parameters.market,
      riskLevel: aiStrategy.parameters.riskLevel,
      style: aiStrategy.parameters.style,
      symbols: aiStrategy.parameters.symbols,
      timeframe: aiStrategy.parameters.timeframe,
      strategyLength: aiStrategy.parameters.strategyLength,
      backtestPeriod: aiStrategy.parameters.backtestPeriod,
      initialCapital: aiStrategy.parameters.initialCapital,
      positionSize: aiStrategy.parameters.positionSize,
      maxPositions: aiStrategy.parameters.maxPositions,
      stopLoss: aiStrategy.parameters.stopLoss,
      takeProfit: aiStrategy.parameters.takeProfit,
      maxDrawdown: aiStrategy.parameters.maxDrawdown,
      commissionRate: aiStrategy.parameters.commissionRate,
      slippage: aiStrategy.parameters.slippage,
      benchmark: aiStrategy.parameters.benchmark
    },
    template: aiStrategy.template ? {
      id: aiStrategy.template.id,
      name: aiStrategy.template.name,
      category: aiStrategy.template.category as StrategyCategory,
      description: aiStrategy.template.description,
      version: '1.0',
      author: aiStrategy.template.metadata?.author || 'AI Generated',
      createdAt: new Date(aiStrategy.template.metadata?.createdAt || Date.now()),
      updatedAt: new Date(aiStrategy.template.metadata?.updatedAt || Date.now()),
      tags: aiStrategy.template.tags || [],
      suitableMarkets: ['CN'],
      suitableTimeframes: ['1d'],
      suitableRiskLevels: [aiStrategy.parameters.riskLevel],
      minCapital: aiStrategy.template.minCapital || 10000,
      maxSymbols: aiStrategy.template.maxSymbols || 10,
      requiredComponents: [],
      defaultParameters: aiStrategy.parameters,
      codeTemplate: aiStrategy.code || '',
      validationRules: [],
      metadata: {
        complexity: 'medium' as 'low' | 'medium' | 'high',
        estimatedBacktestTime: '5-10 minutes',
        dependencies: [],
        performance: {
          expectedReturn: '10-20%',
          maxDrawdown: '5-15%',
          sharpeRatio: '1.0-2.0'
        }
      }
    } : undefined,
    metadata: aiStrategy.metadata || {
      createdAt: new Date(),
      updatedAt: new Date(),
      version: 1,
      tags: [],
      complexity: 5,
      estimatedPerformance: {
        expectedReturn: 0.15,
        expectedDrawdown: 0.10,
        sharpeRatio: 1.2,
        winRate: 0.55
      }
    },
    conversation: aiStrategy.conversation.map(msg => ({
      id: msg.id,
      role: msg.role,
      content: msg.content,
      timestamp: new Date(msg.timestamp),
      type: msg.type || 'text',
      metadata: msg.metadata
    })),
    validation: aiStrategy.validation,
    analysis: aiStrategy.analysis
  };
};

export const convertStrategyToAIStrategy = (strategy: Strategy): AIStrategy => {
  return {
    id: strategy.id,
    name: strategy.name,
    description: strategy.description,
    code: strategy.code,
    parameters: {
      description: strategy.parameters.description,
      style: strategy.parameters.style,
      strategyLength: strategy.parameters.strategyLength,
      backtestPeriod: strategy.parameters.backtestPeriod,
      market: strategy.parameters.market,
      riskLevel: strategy.parameters.riskLevel,
      symbols: strategy.parameters.symbols,
      timeframe: strategy.parameters.timeframe,
      initialCapital: strategy.parameters.initialCapital,
      positionSize: strategy.parameters.positionSize,
      maxPositions: strategy.parameters.maxPositions,
      stopLoss: strategy.parameters.stopLoss,
      takeProfit: strategy.parameters.takeProfit,
      maxDrawdown: strategy.parameters.maxDrawdown,
      commissionRate: strategy.parameters.commissionRate,
      slippage: strategy.parameters.slippage,
      benchmark: strategy.parameters.benchmark
    },
    status: strategy.metadata?.version ? 'active' : 'draft',
    metadata: strategy.metadata,
    conversation: strategy.conversation.map(msg => ({
      id: msg.id,
      role: msg.role,
      content: msg.content,
      timestamp: msg.timestamp.toISOString(),
      type: msg.type,
      metadata: msg.metadata
    })),
    template: strategy.template ? {
      id: strategy.template.id,
      name: strategy.template.name,
      description: strategy.template.description,
      category: strategy.template.category,
      riskLevel: (strategy.template.suitableRiskLevels?.[0] ?? strategy.parameters.riskLevel ?? 'medium') as 'low' | 'medium' | 'high',
      complexity: strategy.template.metadata?.complexity ?? 'medium',
      market: strategy.template.suitableMarkets?.[0] ?? strategy.parameters.market,
      minCapital: strategy.template.minCapital,
      maxSymbols: strategy.template.maxSymbols,
      requiredParams: strategy.template.requiredComponents.map(component => component.name),
      optionalParams: Object.keys(strategy.template.defaultParameters ?? {}),
      codeTemplate: strategy.template.requiredComponents
        .map(component => component.codeTemplate)
        .filter(Boolean)
        .join('\n\n') || strategy.code,
      tags: strategy.template.tags,
      metadata: {
        author: strategy.template.author,
        version: strategy.template.version,
        createdAt: strategy.template.createdAt.toISOString(),
        updatedAt: strategy.template.updatedAt.toISOString(),
        usage_count: 0,
        rating: 0
      }
    } : undefined,
    validation: strategy.validation,
    analysis: strategy.analysis,
    language: strategy.code.includes('python') ? 'python' : 'javascript'
  };
};

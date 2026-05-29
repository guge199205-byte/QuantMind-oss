/**
 * 参数验证器
 * 提供策略参数的验证功能
 */

export interface ValidationResult {
  isValid: boolean;
  errors: string[];
  warnings: string[];
  suggestions: string[];
}

export interface ParameterRule {
  name: string;
  type: 'number' | 'string' | 'array' | 'boolean';
  required: boolean;
  min?: number;
  max?: number;
  pattern?: RegExp;
  options?: any[];
}

// 预定义的验证规则
export const COMMON_STRATEGY_RULES: Record<string, ParameterRule> = {
  initialCapital: {
    name: '初始资金',
    type: 'number',
    required: true,
    min: 1000,
    max: 100000000
  },
  commission: {
    name: '手续费率',
    type: 'number',
    required: false,
    min: 0,
    max: 0.01
  },
  slippage: {
    name: '滑点',
    type: 'number',
    required: false,
    min: 0,
    max: 0.01
  },
  timeframe: {
    name: '时间周期',
    type: 'string',
    required: false,
    options: ['1m', '5m', '15m', '30m', '1h', '1d']
  }
};

export function validateParameters(params: Record<string, any>, rules: Record<string, ParameterRule>): ValidationResult {
  const errors: string[] = [];
  const warnings: string[] = [];

  for (const [paramName, rule] of Object.entries(rules)) {
    const value = params[paramName];

    // 检查必需参数
    if (rule.required && (value === undefined || value === null || value === '')) {
      errors.push(`参数 ${paramName} 是必需的`);
      continue;
    }

    // 如果参数不是必需的且为空，跳过验证
    if (!rule.required && (value === undefined || value === null || value === '')) {
      continue;
    }

    // 类型验证
    if (rule.type === 'number' && typeof value !== 'number') {
      errors.push(`参数 ${paramName} 必须是数字`);
    } else if (rule.type === 'string' && typeof value !== 'string') {
      errors.push(`参数 ${paramName} 必须是字符串`);
    } else if (rule.type === 'array' && !Array.isArray(value)) {
      errors.push(`参数 ${paramName} 必须是数组`);
    } else if (rule.type === 'boolean' && typeof value !== 'boolean') {
      errors.push(`参数 ${paramName} 必须是布尔值`);
    }

    // 范围验证
    if (rule.type === 'number' && typeof value === 'number') {
      if (rule.min !== undefined && value < rule.min) {
        errors.push(`参数 ${paramName} 不能小于 ${rule.min}`);
      }
      if (rule.max !== undefined && value > rule.max) {
        errors.push(`参数 ${paramName} 不能大于 ${rule.max}`);
      }
    }

    // 选项验证
    if (rule.options && !rule.options.includes(value)) {
      errors.push(`参数 ${paramName} 必须是以下值之一: ${rule.options.join(', ')}`);
    }

    // 正则表达式验证
    if (rule.pattern && typeof value === 'string' && !rule.pattern.test(value)) {
      errors.push(`参数 ${paramName} 格式不正确`);
    }
  }

  return {
    isValid: errors.length === 0,
    errors,
    warnings,
    suggestions: []
  };
}

// 参数验证器对象
export const parameterValidator = {
  validate: validateParameters,
  rules: COMMON_STRATEGY_RULES
};

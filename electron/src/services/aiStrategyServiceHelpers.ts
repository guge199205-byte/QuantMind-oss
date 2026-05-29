// AI 策略服务通用工具
import { Strategy, StrategyParams } from '../types/strategy';

interface StrategyMetadata {
  factors?: string[];
  risk_controls?: string[];
  assumptions?: string[];
  notes?: string;
}

export class AIStrategyServiceHelpersMixin {
  private convertToStrategyParams(aiParams: Partial<StrategyParams>): StrategyParams {
    const src = aiParams || {};
    return {
      description: (src.description as string) || '',
      market: (src.market as any) || 'CN',
      riskLevel: (src.riskLevel as any) || 'medium',
      style: (src.style as any) || 'custom',
      symbols: (src.symbols as string[]) || [],
      timeframe: (src.timeframe as any) || '1d',
      strategyLength: (src.strategyLength as any) || 'unlimited',
      backtestPeriod: (src.backtestPeriod as any) || '1year',
      initialCapital: (src.initialCapital as number) || 100000,
      positionSize: (src.positionSize as number) || 0.1,
      maxPositions: (src.maxPositions as number) || 10,
      stopLoss: (src.stopLoss as number) || 0.05,
      takeProfit: (src.takeProfit as number) || 0.1,
      maxDrawdown: (src.maxDrawdown as number | undefined),
      commissionRate: (src.commissionRate as number | undefined),
      slippage: (src.slippage as number | undefined),
      benchmark: (src.benchmark as string | undefined)
    };
  }

  // 类型转换函数：Strategy -> AIStrategy
  private convertToAIStrategy(strategy: Strategy): Strategy & { language: string; framework: string; createdAt: string; performance?: Record<string, number> } {
    const metadata = (strategy as unknown as { metadata?: { performance?: Record<string, number> } }).metadata;
    const performance = strategy.validation ? undefined : (metadata?.performance ?? {
      totalReturn: 0,
      sharpeRatio: 0,
      maxDrawdown: 0,
      winRate: 0,
      profitFactor: 0
    });

    return {
      ...strategy,
      language: 'python',
      framework: 'miniqmt',
      createdAt: new Date().toISOString(),
      performance
    };
  }

  // 生成策略 - 兼容 AIStrategyParams
  async generateStrategy(params: StrategyParams | Partial<StrategyParams>): Promise<Strategy> {
    // 如果传入的是 AIStrategyParams，转换为 StrategyParams
    const strategyParams = this.convertToStrategyParams(params as Partial<StrategyParams>);
    return this.generateStrategyInternal(strategyParams);
  }

  // 内部生成策略方法

  protected async generateStrategyInternal(params: StrategyParams): Promise<Strategy> {
    throw new Error('generateStrategyInternal must be implemented by subclass');
  }

  protected normalizeCode(raw?: string): string {
    if (!raw) {
      return '';
    }

    let code = raw.trim();

    // 移除代码块标记
    if (code.startsWith('```')) {
      const lines = code.split('\n');
      lines.shift();
      if (lines.length && lines[lines.length - 1].trim() === '```') {
        lines.pop();
      }
      code = lines.join('\n');
    }

    // 处理JSON格式的代码
    if (code.startsWith('{') && code.includes('"python_code"')) {
      try {
        const parsed = JSON.parse(code);
        if (parsed?.python_code) {
          return this.normalizeCode(parsed.python_code as string);
        }
      } catch (error) {
        console.warn('无法解析模型返回的JSON代码片段:', error);
        // 尝试从JSON中提取python_code字段 - 改进的正则表达式
        const match = code.match(/"python_code"\s*:\s*"((?:[^"\\]|\\.)*)"/s);
        if (match) {
          try {
            let extracted = match[1];
            // 改进的转义字符解码
            extracted = extracted
              .replace(/\\n/g, '\n')
              .replace(/\\t/g, '\t')
              .replace(/\\"/g, '"')
              .replace(/\\\\/g, '\\')
              .replace(/\\r/g, '\r');
            return this.normalizeCode(extracted);
          } catch (e) {
            console.warn('提取python_code字段失败:', e);
          }
        }

        // 如果正则表达式匹配失败，尝试手动解析
        const pythonCodeIndex = code.indexOf('"python_code"');
        if (pythonCodeIndex !== -1) {
          const startIndex = code.indexOf('"', pythonCodeIndex + 14) + 1;
          let endIndex = startIndex;
          let inString = false;
          let escaped = false;

          // 更健壮的字符串解析逻辑
          for (let i = startIndex; i < code.length; i++) {
            const char = code[i];

            if (escaped) {
              escaped = false;
              continue;
            }

            if (char === '\\') {
              escaped = true;
              continue;
            }

            if (char === '"' && !escaped) {
              if (!inString) {
                inString = true;
              } else {
                endIndex = i;
                break;
              }
            }
          }

          if (endIndex > startIndex) {
            let extracted = code.substring(startIndex, endIndex);
            extracted = extracted
              .replace(/\\n/g, '\n')
              .replace(/\\t/g, '\t')
              .replace(/\\"/g, '"')
              .replace(/\\\\/g, '\\')
              .replace(/\\r/g, '\r');
            return this.normalizeCode(extracted);
          }
        }
      }
    }

    // 处理转义字符
    if (code.includes('\\n') || code.includes('\\t') || code.includes('\\"')) {
      try {
        const wrapped = '"' + code.replace(/\\/g, '\\\\').replace(/"/g, '\\"') + '"';
        code = JSON.parse(wrapped);
      } catch (error) {
        console.warn('无法解码转义字符，尝试手动替换:', error);
        code = code
          .replace(/\\n/g, '\n')
          .replace(/\\t/g, '\t')
          .replace(/\\"/g, '"')
          .replace(/\\r/g, '\r');
      }
    }

    // 改进的代码完整性检查
    const fixedCode = this.ensureCodeCompleteness(code);

    return fixedCode;
  }

  protected ensureCodeCompleteness(code: string): string {
    let fixedCode = code;

    // 检查未闭合的括号和引号
    const stack: string[] = [];
    const pairs: { [key: string]: string } = {
      '{': '}',
      '[': ']',
      '(': ')'
    };

    for (let i = 0; i < fixedCode.length; i++) {
      const char = fixedCode[i];

      if (char in pairs) {
        stack.push(char);
      } else if (char === '}' || char === ']' || char === ')') {
        const lastOpen = stack.pop();
        const expectedClose = pairs[lastOpen];
        if (expectedClose !== char) {
          // 不匹配，将最后一个打开的括号重新放回
          if (lastOpen) {
            stack.push(lastOpen);
          }
        }
      }
    }

    // 补充未闭合的括号
    while (stack.length > 0) {
      const lastOpen = stack.pop();
      if (lastOpen && pairs[lastOpen]) {
        fixedCode += pairs[lastOpen];
        console.log(`补充了闭合括号: ${pairs[lastOpen]}`);
      }
    }

    // 检查字符串引号
    const quoteStack: number[] = [];
    let inString = false;
    let escaped = false;

    for (let i = 0; i < fixedCode.length; i++) {
      const char = fixedCode[i];

      if (escaped) {
        escaped = false;
        continue;
      }

      if (char === '\\') {
        escaped = true;
        continue;
      }

      if (char === '"' && !escaped) {
        if (!inString) {
          inString = true;
          quoteStack.push(i);
        } else {
          inString = false;
          quoteStack.pop();
        }
      }
    }

    // 如果有未闭合的字符串，补充引号
    if (inString) {
      fixedCode += '"';
      console.log('补充了缺失的引号');
    }

    return fixedCode;
  }

  // 获取策略历史

  protected formatAIResponse(
    rationale: string,
    code: string,
    description: string,
    metadata?: StrategyMetadata,
    params?: StrategyParams
  ): string {
    let response = `## ${this.generateStrategyName(description)}\n\n`;

    if (rationale && rationale.trim()) {
      response += `### 策略说明\n${rationale}\n\n`;
    } else {
      response += `### 策略说明\n已为您生成${description}策略。\n\n`;
    }

    if (metadata) {
      if (metadata.factors?.length) {
        response += `### 关键因子\n`;
        metadata.factors.forEach(factor => {
          response += `- ${factor}\n`;
        });
        response += '\n';
      }

      if (metadata.risk_controls?.length) {
        response += `### 风控措施\n`;
        metadata.risk_controls.forEach(control => {
          response += `- ${control}\n`;
        });
        response += '\n';
      }

      if (metadata.assumptions?.length) {
        response += `### 策略假设\n`;
        metadata.assumptions.forEach(item => {
          response += `- ${item}\n`;
        });
        response += '\n';
      }

      if (metadata.notes) {
        response += `### 备注\n${metadata.notes}\n\n`;
      }
    }

    if (code && code.trim()) {
      response += `### 策略代码\n\n`;
      response += `\`\`\`python\n${code}\n\`\`\`\n\n`;
    }

    if (params) {
      response += `### 策略参数\n`;
      response += `- 市场: ${params.market || 'CN'}\n`;
      response += `- 风险级别: ${params.riskLevel || 'medium'}\n`;
      if (params.symbols?.length) {
        response += `- 股票池: ${params.symbols.join(', ')}\n`;
      }
      if (params.timeframe) {
        response += `- 时间周期: ${params.timeframe}\n`;
      }
      if (params.initialCapital) {
        response += `- 初始资金: ${params.initialCapital}\n`;
      }
      if (params.positionSize) {
        response += `- 单次仓位比例: ${params.positionSize}%\n`;
      }
      if (params.maxPositions) {
        response += `- 最大持仓数量: ${params.maxPositions}\n`;
      }
      if (params.stopLoss !== undefined) {
        response += `- 止损: ${params.stopLoss}%\n`;
      }
      if (params.takeProfit !== undefined) {
        response += `- 止盈: ${params.takeProfit}%\n`;
      }
      if (params.strategyLength) {
        response += `- 策略适用期限: ${params.strategyLength}\n`;
      }
      if (params.backtestPeriod) {
        response += `- 回测区间: ${params.backtestPeriod}\n`;
      }
      response += '\n';
    }

    response += `### 使用说明\n`;
    response += `- 您可以在"代码编辑"页面查看完整代码\n`;
    response += `- 点击"一键回测"测试策略效果\n`;
    response += `- 在"AI对话"页面可以继续优化策略\n`;

    return response;
  }

  // 工具方法
  protected generateId(): string {
    return Date.now().toString(36) + Math.random().toString(36).substr(2);
  }

  protected generateStrategyName(description: string): string {
    if (description.includes('均线')) return '均线策略';
    if (description.includes('动量')) return '动量策略';
    if (description.includes('突破')) return '突破策略';
    if (description.includes('套利')) return '套利策略';
    if (description.includes('网格')) return '网格策略';
    return '自定义策略';
  }

  protected extractTags(description: string, riskLevel: string): string[] {
    const tags: string[] = [];
    tags.push(riskLevel === 'low' ? '低风险' : riskLevel === 'high' ? '高风险' : '中风险');
    if (description.includes('均线')) tags.push('均线');
    if (description.includes('动量')) tags.push('动量');
    if (description.includes('突破')) tags.push('突破');
    if (description.includes('套利')) tags.push('套利');
    return tags;
  }


  // 上传文件

  protected saveToLocalStorage(strategy: Strategy): void {
    try {
      const existing = localStorage.getItem('quantmind-strategies');
      const strategies = existing ? JSON.parse(existing) : [];
      const index = strategies.findIndex((s: Strategy) => s.id === strategy.id);
      if (index >= 0) {
        strategies[index] = strategy;
      } else {
        strategies.unshift(strategy);
      }
      localStorage.setItem('quantmind-strategies', JSON.stringify(strategies));
    } catch (error) {
      console.error('保存到本地存储失败:', error);
    }
  }
}

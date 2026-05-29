/**
 * 代码处理器
 * 基于前端改进规划文档实现的代码规范化处理系统
 */

import {
  ValidationResult,
  ValidationContext,
  ValidationError,
  ValidationWarning,
  RealTimeValidationRequest,
  RealTimeValidationResponse,
  CodeAnalysis,
  GenerationStage
} from '../types/strategy';

// Python语法检查器
export class PythonSyntaxChecker {
  /**
   * 检查Python语法
   */
  checkSyntax(code: string): ValidationError[] {
    const errors: ValidationError[] = [];

    try {
      // 基础语法检查
      this.checkBasicSyntax(code, errors);

      // 函数定义检查
      this.checkFunctionDefinitions(code, errors);

      // 导入语句检查
      this.checkImports(code, errors);

      // 缩进检查
      this.checkIndentation(code, errors);

      // 括号匹配检查
      this.checkBrackets(code, errors);

    } catch (error) {
      errors.push({
        line: 0,
        column: 0,
        message: `语法检查失败: ${error instanceof Error ? error.message : String(error)}`,
        type: 'syntax',
        severity: 'error'
      });
    }

    return errors;
  }

  private checkBasicSyntax(code: string, errors: ValidationError[]): void {
    const lines = code.split('\n');

    lines.forEach((line, index) => {
      const lineNum = index + 1;
      const trimmed = line.trim();

      // 检查未闭合的字符串
      if (this.hasUnclosedString(trimmed)) {
        errors.push({
          line: lineNum,
          column: 0,
          message: '字符串未正确闭合',
          type: 'syntax',
          severity: 'error'
        });
      }

      // 检查冒号使用
      if (trimmed.match(/^(if|elif|else|for|while|def|class|try|except|finally|with)\b[^:]*$/)) {
        errors.push({
          line: lineNum,
          column: trimmed.length,
          message: '缺少冒号',
          type: 'syntax',
          severity: 'error'
        });
      }
    });
  }

  private checkFunctionDefinitions(code: string, errors: ValidationError[]): void {
    const lines = code.split('\n');
    let inFunction = false;
    let functionIndent = 0;

    lines.forEach((line, index) => {
      const lineNum = index + 1;
      const trimmed = line.trim();
      const indent = line.length - line.trimStart().length;

      // 检查函数定义
      if (trimmed.startsWith('def ')) {
        inFunction = true;
        functionIndent = indent;

        // 检查函数名
        const funcMatch = trimmed.match(/def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(/);
        if (!funcMatch) {
          errors.push({
            line: lineNum,
            column: trimmed.indexOf('def ') + 4,
            message: '函数名格式不正确',
            type: 'syntax',
            severity: 'error'
          });
        }
      }

      // 检查函数体缩进
      if (inFunction && trimmed !== '' && !trimmed.startsWith('#')) {
        if (indent <= functionIndent && !trimmed.startsWith('def ') && !trimmed.startsWith('class ')) {
          inFunction = false;
        } else if (indent === functionIndent + 4 && !trimmed.match(/^(if|elif|else|for|while|try|except|finally|with|def|class)\b/)) {
          // 这是正常的第一级缩进
        } else if (indent > functionIndent + 4 && !trimmed.match(/^(if|elif|else|for|while|try|except|finally|with|def|class)\b/)) {
          // 这是更深层级的缩进
        }
      }
    });
  }

  private checkImports(code: string, errors: ValidationError[]): void {
    const lines = code.split('\n');

    lines.forEach((line, index) => {
      const lineNum = index + 1;
      const trimmed = line.trim();

      // 检查import语句
      if (trimmed.startsWith('import ')) {
        if (!trimmed.match(/^import\s+[a-zA-Z_][a-zA-Z0-9_]*(\s+as\s+[a-zA-Z_][a-zA-Z0-9_]*)?(,\s*[a-zA-Z_][a-zA-Z0-9_]*(\s+as\s+[a-zA-Z_][a-zA-Z0-9_]*)?)*$/)) {
          errors.push({
            line: lineNum,
            column: 0,
            message: 'import语句格式不正确',
            type: 'syntax',
            severity: 'error'
          });
        }
      }

      // 检查from...import语句
      if (trimmed.startsWith('from ')) {
        if (!trimmed.match(/^from\s+[a-zA-Z_.][a-zA-Z0-9_.]*\s+import\s+(\*|[a-zA-Z_][a-zA-Z0-9_]*(\s+as\s+[a-zA-Z_][a-zA-Z0-9_]*)?(,\s*[a-zA-Z_][a-zA-Z0-9_]*(\s+as\s+[a-zA-Z_][a-zA-Z0-9_]*)?)*)$/)) {
          errors.push({
            line: lineNum,
            column: 0,
            message: 'from...import语句格式不正确',
            type: 'syntax',
            severity: 'error'
          });
        }
      }
    });
  }

  private checkIndentation(code: string, errors: ValidationError[]): void {
    const lines = code.split('\n');

    lines.forEach((line, index) => {
      const lineNum = index + 1;
      const trimmed = line.trim();

      if (trimmed === '' || trimmed.startsWith('#')) {
        return;
      }

      const leadingSpaces = line.length - line.trimStart().length;

      // 检查是否使用空格缩进（应该是4个空格的倍数）
      if (leadingSpaces % 4 !== 0) {
        errors.push({
          line: lineNum,
          column: 0,
          message: '缩进应该是4个空格的倍数',
          type: 'syntax',
          severity: 'warning'
        });
      }
    });
  }

  private checkBrackets(code: string, errors: ValidationError[]): void {
    const lines = code.split('\n');
    const bracketStack: { char: string; line: number; column: number }[] = [];

    lines.forEach((line, index) => {
      const lineNum = index + 1;

      for (let i = 0; i < line.length; i++) {
        const char = line[i];

        if (char === '(' || char === '[' || char === '{') {
          bracketStack.push({ char, line: lineNum, column: i + 1 });
        } else if (char === ')' || char === ']' || char === '}') {
          const last = bracketStack.pop();
          if (!last) {
            errors.push({
              line: lineNum,
              column: i + 1,
              message: `未匹配的右括号: ${char}`,
              type: 'syntax',
              severity: 'error'
            });
          } else if (
            (last.char === '(' && char !== ')') ||
            (last.char === '[' && char !== ']') ||
            (last.char === '{' && char !== '}')
          ) {
            errors.push({
              line: lineNum,
              column: i + 1,
              message: `括号不匹配: 期望 ${this.getMatchingBracket(last.char)}，实际 ${char}`,
              type: 'syntax',
              severity: 'error'
            });
          }
        }
      }
    });

    // 检查未闭合的左括号
    bracketStack.forEach(item => {
      errors.push({
        line: item.line,
        column: item.column,
        message: `未闭合的左括号: ${item.char}`,
        type: 'syntax',
        severity: 'error'
      });
    });
  }

  private hasUnclosedString(line: string): boolean {
    const quotes = ["'", '"', '"""', '"""'];
    let inString = false;
    let stringChar = '';
    let i = 0;

    while (i < line.length) {
      if (!inString && quotes.includes(line.substring(i, i + 1))) {
        inString = true;
        stringChar = line.substring(i, i + 1);
        i += stringChar.length;
      } else if (inString && line.substring(i, i + stringChar.length) === stringChar) {
        inString = false;
        i += stringChar.length;
      } else {
        i++;
      }
    }

    return inString;
  }

  private getMatchingBracket(char: string): string {
    switch (char) {
      case '(': return ')';
      case '[': return ']';
      case '{': return '}';
      default: return '';
    }
  }
}

// 逻辑验证器
export class LogicValidator {
  /**
   * 验证策略逻辑
   */
  validateLogic(code: string, context: ValidationContext): ValidationError[] {
    const errors: ValidationError[] = [];

    try {
      // 检查必要的函数
      this.checkRequiredFunctions(code, context, errors);

      // 检查风险控制
      this.checkRiskControls(code, context, errors);

      // 检查数据验证
      this.checkDataValidation(code, errors);

      // 检查错误处理
      this.checkErrorHandling(code, errors);

      // 检查变量使用
      this.checkVariableUsage(code, errors);

    } catch (error) {
      errors.push({
        line: 0,
        column: 0,
        message: `逻辑验证失败: ${error instanceof Error ? error.message : String(error)}`,
        type: 'logic',
        severity: 'error'
      });
    }

    return errors;
  }

  private checkRequiredFunctions(code: string, context: ValidationContext, errors: ValidationError[]): void {
    const requiredFunctions = ['initialize', 'handle_data'];
    const functions = this.extractFunctions(code);

    requiredFunctions.forEach(funcName => {
      if (!functions.includes(funcName)) {
        errors.push({
          line: 0,
          column: 0,
          message: `缺少必要函数: ${funcName}`,
          type: 'logic',
          severity: 'error'
        });
      }
    });
  }

  private checkRiskControls(code: string, context: ValidationContext, errors: ValidationError[]): void {
    const hasStopLoss = code.includes('stop_loss') || code.includes('止损');
    const hasPositionControl = code.includes('position') || code.includes('仓位');

    if (!hasStopLoss) {
      errors.push({
        line: 0,
        column: 0,
        message: '策略缺少止损机制',
        type: 'logic',
        severity: 'warning'
      });
    }

    if (!hasPositionControl) {
      errors.push({
        line: 0,
        column: 0,
        message: '策略缺少仓位控制',
        type: 'logic',
        severity: 'warning'
      });
    }

    // 检查是否有合理的止损比例
    const stopLossMatch = code.match(/stop_loss\s*=\s*([0-9.]+)/);
    if (stopLossMatch && parseFloat(stopLossMatch[1]) > 0.2) {
      errors.push({
        line: 0,
        column: 0,
        message: '止损比例过高（>20%），建议控制在10%以内',
        type: 'logic',
        severity: 'warning'
      });
    }
  }

  private checkDataValidation(code: string, errors: ValidationError[]): void {
    // 检查是否有数据完整性检查
    const hasDataCheck = code.includes('len(') || code.includes('notna') || code.includes('isnull');

    if (!hasDataCheck) {
      errors.push({
        line: 0,
        column: 0,
        message: '建议添加数据完整性检查',
        type: 'logic',
        severity: 'warning'
      });
    }

    // 检查是否处理了空数据情况
    const hasEmptyDataHandling = code.includes('if len') || code.includes('if not');

    if (!hasEmptyDataHandling) {
      errors.push({
        line: 0,
        column: 0,
        message: '建议添加空数据处理逻辑',
        type: 'logic',
        severity: 'warning'
      });
    }
  }

  private checkErrorHandling(code: string, errors: ValidationError[]): void {
    // 检查是否有try-except块
    const hasTryExcept = code.includes('try:') && code.includes('except');

    if (!hasTryExcept) {
      errors.push({
        line: 0,
        column: 0,
        message: '建议添加异常处理机制',
        type: 'logic',
        severity: 'warning'
      });
    }
  }

  private checkVariableUsage(code: string, errors: ValidationError[]): void {
    const lines = code.split('\n');
    const definedVars = new Set<string>();
    const usedVars = new Set<string>();

    lines.forEach((line, index) => {
      const trimmed = line.trim();
      const lineNum = index + 1;

      // 检查变量定义
      const assignMatch = trimmed.match(/^([a-zA-Z_][a-zA-Z0-9_]*)\s*=/);
      if (assignMatch) {
        definedVars.add(assignMatch[1]);
      }

      // 检查函数参数定义
      const funcMatch = trimmed.match(/def\s+[a-zA-Z_][a-zA-Z0-9_]*\s*\(([^)]*)\)/);
      if (funcMatch) {
        const params = funcMatch[1].split(',').map(p => p.trim().split('=')[0]);
        params.forEach(param => {
          if (param && param !== 'self') {
            definedVars.add(param);
          }
        });
      }
    });

    // 第二遍检查变量使用
    lines.forEach(line => {
      const words = line.split(/[^a-zA-Z0-9_]/);
      words.forEach(word => {
        if (word && definedVars.has(word)) {
          usedVars.add(word);
        }
      });
    });

    // 检查未使用的变量
    definedVars.forEach(varName => {
      if (!usedVars.has(varName) && varName !== 'context' && varName !== 'data') {
        errors.push({
          line: 0,
          column: 0,
          message: `定义但未使用的变量: ${varName}`,
          type: 'logic',
          severity: 'warning'
        });
      }
    });
  }

  private extractFunctions(code: string): string[] {
    const functions: string[] = [];
    const lines = code.split('\n');

    lines.forEach(line => {
      const match = line.match(/def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(/);
      if (match) {
        functions.push(match[1]);
      }
    });

    return functions;
  }
}

// 代码格式化器
export class CodeFormatter {
  /**
   * 格式化Python代码
   */
  formatCode(code: string): string {
    try {
      let formatted = code;

      // 标准化缩进（4个空格）
      formatted = this.standardizeIndentation(formatted);

      // 标准化引号（使用单引号）
      formatted = this.standardizeQuotes(formatted);

      // 标准化空格
      formatted = this.standardizeSpaces(formatted);

      // 标准化空行
      formatted = this.standardizeEmptyLines(formatted);

      // 标准化导入语句
      formatted = this.standardizeImports(formatted);

      return formatted;
    } catch (error) {
      console.error('代码格式化失败:', error);
      return code;
    }
  }

  private standardizeIndentation(code: string): string {
    const lines = code.split('\n');
    const formatted: string[] = [];
    let currentIndent = 0;

    lines.forEach(line => {
      const trimmed = line.trim();

      if (trimmed === '') {
        formatted.push('');
        return;
      }

      // 减少缩进的情况
      if (trimmed.match(/^(elif|else|except|finally)\b/) ||
          (currentIndent > 0 && !trimmed.match(/^(if|elif|else|for|while|try|except|finally|with|def|class)\b/) && !trimmed.startsWith('#'))) {
        currentIndent = Math.max(0, currentIndent - 4);
      }

      formatted.push(' '.repeat(currentIndent) + trimmed);

      // 增加缩进的情况
      if (trimmed.endsWith(':') && !trimmed.startsWith('#')) {
        currentIndent += 4;
      }
    });

    return formatted.join('\n');
  }

  private standardizeQuotes(code: string): string {
    // 将双引号转换为单引号（除了字符串中包含单引号的情况）
    return code.replace(/"([^'"]*)"/g, "'$1'");
  }

  private standardizeSpaces(code: string): string {
    // 标准化运算符周围的空格
    let formatted = code.replace(/([=!<>]=?)\s*=/g, '$1 =');
    formatted = formatted.replace(/([=!<>])\s*=/g, '$1 =');
    formatted = formatted.replace(/=\s*([=!<>])/g, '= $1');
    formatted = formatted.replace(/([+\-*/])\s*=/g, '$1 =');
    formatted = formatted.replace(/=\s*([+\-*/])/g, '= $1');

    // 标准化逗号后的空格
    formatted = formatted.replace(/,([^\s])/g, ', $1');

    // 标准化函数调用的空格
    formatted = formatted.replace(/(\w+)\s*\(/g, '$1(');

    return formatted;
  }

  private standardizeEmptyLines(code: string): string {
    const lines = code.split('\n');
    const formatted: string[] = [];
    let prevEmpty = false;

    lines.forEach(line => {
      const isEmpty = line.trim() === '';

      if (isEmpty) {
        if (!prevEmpty) {
          formatted.push('');
        }
        prevEmpty = true;
      } else {
        formatted.push(line);
        prevEmpty = false;
      }
    });

    return formatted.join('\n');
  }

  private standardizeImports(code: string): string {
    const lines = code.split('\n');
    const imports: string[] = [];
    const others: string[] = [];
    let inImportSection = true;

    lines.forEach(line => {
      const trimmed = line.trim();

      if (trimmed === '' || trimmed.startsWith('import ') || trimmed.startsWith('from ')) {
        if (inImportSection) {
          imports.push(line);
        } else {
          others.push(line);
        }
      } else {
        inImportSection = false;
        others.push(line);
      }
    });

    // 排序import语句
    imports.sort((a, b) => {
      const aTrim = a.trim();
      const bTrim = b.trim();

      // 标准库import在前
      const aIsStd = !aTrim.includes('.');
      const bIsStd = !bTrim.includes('.');

      if (aIsStd && !bIsStd) return -1;
      if (!aIsStd && bIsStd) return 1;

      return aTrim.localeCompare(bTrim);
    });

    return [...imports, '', ...others].join('\n').replace(/\n{3,}/g, '\n\n');
  }
}

// 代码分析器
export class CodeAnalyzer {
  /**
   * 分析代码质量
   */
  analyzeCode(code: string): CodeAnalysis {
    return {
      missingRiskControls: this.checkMissingRiskControls(code),
      performanceIssues: this.checkPerformanceIssues(code),
      dataValidationGaps: this.checkDataValidationGaps(code),
      errorHandling: this.checkErrorHandling(code),
      dependencies: this.extractDependencies(code),
      complexity: this.calculateComplexity(code),
      maintainability: this.calculateMaintainability(code)
    };
  }

  private checkMissingRiskControls(code: string): string[] {
    const issues: string[] = [];

    if (!code.includes('stop_loss')) {
      issues.push('缺少止损机制');
    }

    if (!code.includes('position')) {
      issues.push('缺少仓位控制');
    }

    if (!code.includes('max_drawdown')) {
      issues.push('缺少最大回撤控制');
    }

    return issues;
  }

  private checkPerformanceIssues(code: string): string[] {
    const issues: string[] = [];

    if (code.includes('for') && code.includes('range(len(')) {
      issues.push('使用了range(len())模式，建议使用enumerate');
    }

    if (code.match(/\.append\(.*\)\s*for/)) {
      issues.push('在循环中使用append，建议使用列表推导式');
    }

    return issues;
  }

  private checkDataValidationGaps(code: string): string[] {
    const issues: string[] = [];

    if (!code.includes('if len(')) {
      issues.push('缺少数据长度检查');
    }

    if (!code.includes('isnull') && !code.includes('notna')) {
      issues.push('缺少空值检查');
    }

    return issues;
  }

  private checkErrorHandling(code: string): string[] {
    const issues: string[] = [];

    if (!code.includes('try:')) {
      issues.push('缺少异常处理');
    }

    return issues;
  }

  private extractDependencies(code: string): string[] {
    const dependencies: string[] = [];
    const lines = code.split('\n');

    lines.forEach(line => {
      const trimmed = line.trim();

      if (trimmed.startsWith('import ')) {
        const module = trimmed.replace('import ', '').split(' as ')[0];
        dependencies.push(module);
      } else if (trimmed.startsWith('from ')) {
        const match = trimmed.match(/from\s+([^\s]+)\s+import/);
        if (match) {
          dependencies.push(match[1]);
        }
      }
    });

    return dependencies;
  }

  private calculateComplexity(code: string): number {
    // 简单的复杂度计算
    let complexity = 1;

    complexity += (code.match(/\bif\b/g) || []).length;
    complexity += (code.match(/\belif\b/g) || []).length;
    complexity += (code.match(/\bfor\b/g) || []).length;
    complexity += (code.match(/\bwhile\b/g) || []).length;
    complexity += (code.match(/\btry\b/g) || []).length;

    return complexity;
  }

  private calculateMaintainability(code: string): number {
    // 简单的可维护性评分（0-100）
    let score = 100;

    const lines = code.split('\n');
    const codeLines = lines.filter(line => line.trim() !== '' && !line.trim().startsWith('#'));

    if (codeLines.length > 100) score -= 10;
    if (codeLines.length > 200) score -= 20;
    if (codeLines.length > 500) score -= 30;

    const maxLineLength = Math.max(...lines.map(line => line.length));
    if (maxLineLength > 80) score -= 10;
    if (maxLineLength > 100) score -= 10;

    return Math.max(0, score);
  }
}

// 实时代码验证器
export class RealTimeValidator {
  private syntaxChecker: PythonSyntaxChecker;
  private logicValidator: LogicValidator;
  private codeAnalyzer: CodeAnalyzer;

  constructor() {
    this.syntaxChecker = new PythonSyntaxChecker();
    this.logicValidator = new LogicValidator();
    this.codeAnalyzer = new CodeAnalyzer();
  }

  /**
   * 实时验证代码
   */
  async validateCode(request: RealTimeValidationRequest): Promise<RealTimeValidationResponse> {
    const startTime = Date.now();

    try {
      // 并行执行各种检查
      const [syntaxErrors, logicErrors] = await Promise.all([
        Promise.resolve(this.syntaxChecker.checkSyntax(request.code)),
        Promise.resolve(this.logicValidator.validateLogic(request.code, request.context))
      ]);

      const allErrors = [...syntaxErrors, ...logicErrors];
      const warnings = allErrors.filter(e => e.severity === 'warning');
      const errors = allErrors.filter(e => e.severity === 'error');

      // 生成建议
      const suggestions = this.generateSuggestions(request.code, errors, warnings as unknown as ValidationWarning[]);

      return {
        isValid: errors.length === 0,
        errors,
        warnings: warnings as any,
        suggestions,
        processingTime: Date.now() - startTime
      };
    } catch (error) {
      return {
        isValid: false,
        errors: [{
          line: 0,
          column: 0,
          message: `验证失败: ${error instanceof Error ? error.message : String(error)}`,
          type: 'syntax',
          severity: 'error'
        }],
        warnings: [],
        suggestions: [],
        processingTime: Date.now() - startTime
      };
    }
  }

  private generateSuggestions(code: string, errors: ValidationError[], warnings: ValidationWarning[]): string[] {
    const suggestions: string[] = [];

    if (errors.some(e => e.message.includes('括号'))) {
      suggestions.push('检查括号是否匹配');
    }

    if (errors.some(e => e.message.includes('缩进'))) {
      suggestions.push('使用4个空格进行缩进');
    }

    if (warnings.some(w => w.message.includes('止损'))) {
      suggestions.push('添加止损机制以控制风险');
    }

    if (warnings.some(w => w.message.includes('仓位'))) {
      suggestions.push('设置合理的仓位控制');
    }

    return suggestions;
  }
}

// 导出主要处理器
export const codeProcessor = {
  syntaxChecker: new PythonSyntaxChecker(),
  logicValidator: new LogicValidator(),
  formatter: new CodeFormatter(),
  analyzer: new CodeAnalyzer(),
  realTimeValidator: new RealTimeValidator()
};

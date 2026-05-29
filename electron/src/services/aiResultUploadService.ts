/**
 * AI策略结果上传服务
 * 专门用于将大模型生成的策略结果保存到腾讯云COS
 */

import { cosUploadService, UploadOptions, UploadResult } from './cosUploadService';

export interface AIStrategyResult {
  id: string;
  prompt: string;
  generatedCode: string;
  parsedCode?: string;
  metadata: {
    model: string;
    timestamp: number;
    strategyType: string;
    parameters: Record<string, any>;
  };
  validation?: {
    isValid: boolean;
    errors: string[];
    warnings: string[];
  };
}

export interface UploadProgress {
  fileType: 'json' | 'python' | 'log';
  progress: number;
  status: 'uploading' | 'success' | 'error';
  message?: string;
}

class AIResultUploadService {
  private basePath = 'ai-strategies';

  /**
   * 上传AI生成的策略结果到COS
   */
  async uploadAIStrategyResult(result: AIStrategyResult): Promise<{
    jsonUrl: string;
    pythonUrl?: string;
    logUrl?: string;
    uploadResults: UploadResult[];
  }> {
    const uploadResults: UploadResult[] = [];
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const strategyId = result.id || `strategy_${timestamp}`;

    try {
      console.log(`开始上传AI策略结果: ${strategyId}`);

      // 1. 上传原始JSON文件（包含大模型的完整输出）
      const jsonResult = await this.uploadJSONFile(result, strategyId);
      uploadResults.push(jsonResult);

      // 2. 上传解析后的Python代码文件
      let pythonResult: UploadResult | undefined;
      if (result.parsedCode) {
        pythonResult = await this.uploadPythonFile(result, strategyId);
        if (pythonResult) uploadResults.push(pythonResult);
      }

      // 3. 上传生成日志文件
      const logResult = await this.uploadLogFile(result, strategyId);
      uploadResults.push(logResult);

      return {
        jsonUrl: jsonResult.fileUrl,
        pythonUrl: pythonResult?.fileUrl,
        logUrl: logResult.fileUrl,
        uploadResults
      };

    } catch (error) {
      console.error('上传AI策略结果失败:', error);
      throw new Error(`上传失败: ${error instanceof Error ? error.message : '未知错误'}`);
    }
  }

  /**
   * 上传JSON文件（大模型原始输出）
   */
  private async uploadJSONFile(result: AIStrategyResult, strategyId: string): Promise<UploadResult> {
    const jsonContent = JSON.stringify({
      id: result.id,
      prompt: result.prompt,
      generatedCode: result.generatedCode,
      metadata: result.metadata,
      validation: result.validation,
      uploadTime: Date.now()
    }, null, 2);

    const fileName = `${strategyId}_raw.json`;
    const filePath = `${this.basePath}/json/${fileName}`;

    const options: UploadOptions = {
      fileName: filePath,
      fileContent: jsonContent,
      fileType: 'application/json'
    };

    return await cosUploadService.uploadFile(options);
  }

  /**
   * 上传Python代码文件（解析后的策略代码）
   */
  private async uploadPythonFile(result: AIStrategyResult, strategyId: string): Promise<UploadResult> {
    if (!result.parsedCode) {
      throw new Error('没有解析后的Python代码');
    }

    const fileName = `${strategyId}_strategy.py`;
    const filePath = `${this.basePath}/python/${fileName}`;

    // 添加文件头注释
    const pythonCode = this.addPythonFileHeader(result, result.parsedCode);

    const options: UploadOptions = {
      fileName: filePath,
      fileContent: pythonCode,
      fileType: 'text/x-python'
    };

    return await cosUploadService.uploadFile(options);
  }

  /**
   * 上传日志文件
   */
  private async uploadLogFile(result: AIStrategyResult, strategyId: string): Promise<UploadResult> {
    const logContent = this.generateLogContent(result);
    const fileName = `${strategyId}_log.txt`;
    const filePath = `${this.basePath}/logs/${fileName}`;

    const options: UploadOptions = {
      fileName: filePath,
      fileContent: logContent,
      fileType: 'text/plain'
    };

    return await cosUploadService.uploadFile(options);
  }

  /**
   * 添加Python文件头注释
   */
  private addPythonFileHeader(result: AIStrategyResult, code: string): string {
    const header = `"""
# -*- coding: utf-8 -*-
"""
AI生成策略代码
策略ID: ${result.id}
生成时间: ${new Date(result.metadata.timestamp).toLocaleString()}
使用模型: ${result.metadata.model}
策略类型: ${result.metadata.strategyType}

# 免责声明
# 本策略由AI生成，仅供学习和研究使用，不构成投资建议

# 风险提示
# 策略存在风险，请充分理解后再使用
"""

# 策略参数
${this.formatParameters(result.metadata.parameters)}

`;

    return header + code;
  }

  /**
   * 格式化策略参数
   */
  private formatParameters(parameters: Record<string, any>): string {
    if (!parameters || Object.keys(parameters).length === 0) {
      return '# 无参数配置';
    }

    let paramCode = '# 策略参数配置\\n';
    Object.entries(parameters).forEach(([key, value]) => {
      paramCode += `# ${key}: ${JSON.stringify(value)}\\n`;
    });

    return paramCode;
  }

  /**
   * 生成日志内容
   */
  private generateLogContent(result: AIStrategyResult): string {
    const logEntries = [
      `=== AI策略生成日志 ===`,
      `生成时间: ${new Date(result.metadata.timestamp).toISOString()}`,
      `策略ID: ${result.id}`,
      `使用模型: ${result.metadata.model}`,
      `策略类型: ${result.metadata.strategyType}`,
      `原始提示词长度: ${result.prompt.length} 字符`,
      `生成代码长度: ${result.generatedCode.length} 字符`,
      `解析代码长度: ${result.parsedCode?.length || 0} 字符`,
      ``,
      `=== 验证结果 ===`,
      `是否有效: ${result.validation?.isValid ? '是' : '否'}`,
      `错误数量: ${result.validation?.errors.length || 0}`,
      `警告数量: ${result.validation?.warnings.length || 0}`,
      ``,
      `=== 错误信息 ===`,
      ...(result.validation?.errors.map((error, index) => `${index + 1}. ${error}`) || ['无错误']),
      ``,
      `=== 警告信息 ===`,
      ...(result.validation?.warnings.map((warning, index) => `${index + 1}. ${warning}`) || ['无警告']),
      ``,
      `=== 上传信息 ===`,
      `上传时间: ${new Date().toISOString()}`,
      `存储路径: ${this.basePath}`
    ];

    return logEntries.join('\\n');
  }

  /**
   * 批量上传策略结果
   */
  async batchUploadStrategyResults(results: AIStrategyResult[]): Promise<{
    success: number;
    failed: number;
    total: number;
    details: Array<{
      strategyId: string;
      success: boolean;
      urls?: { json: string; python?: string; log: string };
      error?: string;
    }>;
  }> {
    const details: Array<{
      strategyId: string;
      success: boolean;
      urls?: { json: string; python?: string; log: string };
      error?: string;
    }> = [];

    let successCount = 0;
    let failedCount = 0;

    for (const result of results) {
      try {
        const uploadResult = await this.uploadAIStrategyResult(result);

        details.push({
          strategyId: result.id,
          success: true,
          urls: {
            json: uploadResult.jsonUrl,
            python: uploadResult.pythonUrl,
            log: uploadResult.logUrl
          }
        });
        successCount++;

        console.log(`策略 ${result.id} 上传成功`);

      } catch (error) {
        details.push({
          strategyId: result.id,
          success: false,
          error: error instanceof Error ? error.message : '上传失败'
        });
        failedCount++;

        console.error(`策略 ${result.id} 上传失败:`, error);
      }
    }

    return {
      success: successCount,
      failed: failedCount,
      total: results.length,
      details
    };
  }

  /**
   * 检查COS配置是否有效
   */
  validateCOSConfig(): boolean {
    return cosUploadService.validateConfig();
  }

  /**
   * 获取上传进度（如果需要实时进度反馈）
   */
  async getUploadProgress(_strategyId: string): Promise<UploadProgress[]> {
    // 这里可以实现实时进度查询
    // 简化实现，返回固定进度
    return [
      { fileType: 'json', progress: 100, status: 'success', message: '上传完成' },
      { fileType: 'python', progress: 100, status: 'success', message: '上传完成' },
      { fileType: 'log', progress: 100, status: 'success', message: '上传完成' }
    ];
  }

  /**
   * 生成文件命名规则
   */
  generateFileName(strategyId: string, fileType: 'json' | 'python' | 'log'): string {
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const extensions = {
      json: '.json',
      python: '.py',
      log: '.txt'
    };

    return `${strategyId}_${timestamp}_${fileType}${extensions[fileType]}`;
  }

  /**
   * 构建存储路径
   */
  buildStoragePath(strategyId: string, fileType: 'json' | 'python' | 'log'): string {
    const directories = {
      json: 'json',
      python: 'python',
      log: 'logs'
    };

    const fileName = this.generateFileName(strategyId, fileType);
    return `${this.basePath}/${directories[fileType]}/${fileName}`;
  }
}

// 创建全局实例
export const aiResultUploadService = new AIResultUploadService();

export default AIResultUploadService;

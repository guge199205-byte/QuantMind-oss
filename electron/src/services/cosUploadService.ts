/**
 * 腾讯云COS文件上传服务
 * 支持大文件分片上传、进度监控、错误重试等功能
 */

// COS配置接口
export interface COSConfig {
  secretId: string;
  secretKey: string;
  bucket: string;
  region: string;
  baseUrl?: string;
}

// 上传选项接口
export interface UploadOptions {
  fileName: string;
  fileContent: string | Blob;
  fileType?: string;
  progressCallback?: (progress: number) => void;
  onSuccess?: (result: UploadResult) => void;
  onError?: (error: Error) => void;
}

// 上传结果接口
export interface UploadResult {
  success: boolean;
  fileUrl: string;
  fileKey: string;
  fileSize: number;
  uploadTime: number;
  message?: string;
}

// 分片上传配置
interface ChunkUploadConfig {
  chunkSize: number;
  maxRetries: number;
  timeout: number;
}

class COSUploadService {
  private config: COSConfig;
  private chunkConfig: ChunkUploadConfig;

  constructor(config: COSConfig) {
    this.config = config;
    this.chunkConfig = {
      chunkSize: 1024 * 1024, // 1MB分片
      maxRetries: 3,
      timeout: 30000 // 30秒超时
    };
  }

  private getPublicBaseUrl(): string {
    return this.config.baseUrl || '';
  }

  /**
   * 上传文件到腾讯云COS
   */
  async uploadFile(options: UploadOptions): Promise<UploadResult> {
    const {
      fileName,
      fileContent,
      fileType = 'text/plain',
      progressCallback,
      onSuccess,
      onError
    } = options;

    try {
      console.log(`开始上传文件到COS: ${fileName}`);

      // 检查文件大小，决定是否使用分片上传
      const fileSize = this.getFileSize(fileContent);
      const useChunkUpload = fileSize > this.chunkConfig.chunkSize;

      let result: UploadResult;

      if (useChunkUpload) {
        console.log(`文件较大(${this.formatFileSize(fileSize)})，使用分片上传`);
        result = await this.uploadWithChunks(fileName, fileContent, fileType, progressCallback);
      } else {
        console.log(`文件较小(${this.formatFileSize(fileSize)})，使用普通上传`);
        result = await this.uploadDirectly(fileName, fileContent, fileType);
      }

      if (progressCallback) {
        progressCallback(100);
      }

      if (onSuccess) {
        onSuccess(result);
      }

      console.log(`文件上传成功: ${result.fileUrl}`);
      return result;

    } catch (error) {
      console.error('文件上传失败:', error);

      const errorResult: UploadResult = {
        success: false,
        fileUrl: '',
        fileKey: '',
        fileSize: 0,
        uploadTime: 0,
        message: error instanceof Error ? error.message : '上传失败'
      };

      if (onError) {
        onError(error instanceof Error ? error : new Error('上传失败'));
      }

      return errorResult;
    }
  }

  /**
   * 直接上传小文件
   */
  private async uploadDirectly(
    fileName: string,
    fileContent: string | Blob,
    fileType: string
  ): Promise<UploadResult> {
    const fileKey = this.generateFileKey(fileName);
    const formData = new FormData();

    // 创建Blob对象
    const blob = typeof fileContent === 'string'
      ? new Blob([fileContent], { type: fileType })
      : fileContent;

    formData.append('file', blob, fileName);

    // 添加必要的参数
    formData.append('key', fileKey);
    formData.append('success_action_status', '200');

    const url = this.getUploadURL(fileKey);
    const timestamp = Math.floor(Date.now() / 1000);
    const authorization = this.generateAuthorization('POST', fileKey, timestamp);

    const response = await fetch(url, {
      method: 'POST',
      body: formData,
      headers: {
        'Authorization': authorization,
        'x-cos-timestamp': timestamp.toString()
      }
    });

    if (!response.ok) {
      throw new Error(`上传失败: ${response.status} ${response.statusText}`);
    }

    return {
      success: true,
      fileUrl: `${this.getPublicBaseUrl()}/${fileKey}`,
      fileKey,
      fileSize: blob.size,
      uploadTime: Date.now()
    };
  }

  /**
   * 分片上传大文件
   */
  private async uploadWithChunks(
    fileName: string,
    fileContent: string | Blob,
    fileType: string,
    progressCallback?: (progress: number) => void
  ): Promise<UploadResult> {
    const fileKey = this.generateFileKey(fileName);
    const blob = typeof fileContent === 'string'
      ? new Blob([fileContent], { type: fileType })
      : fileContent;

    const fileSize = blob.size;
    const totalChunks = Math.ceil(fileSize / this.chunkConfig.chunkSize);
    let uploadedSize = 0;

    console.log(`开始分片上传，总大小: ${this.formatFileSize(fileSize)}, 分片数: ${totalChunks}`);

    // 初始化分片上传
    const uploadId = await this.initMultipartUpload(fileKey);

    const uploadedParts: Array<{ PartNumber: number; ETag: string }> = [];

    for (let chunkIndex = 0; chunkIndex < totalChunks; chunkIndex++) {
      const start = chunkIndex * this.chunkConfig.chunkSize;
      const end = Math.min(start + this.chunkConfig.chunkSize, fileSize);
      const chunk = blob.slice(start, end);

      let retries = 0;
      let success = false;

      while (retries < this.chunkConfig.maxRetries && !success) {
        try {
          const partNumber = chunkIndex + 1;
          const etag = await this.uploadPart(fileKey, uploadId, partNumber, chunk);

          uploadedParts.push({ PartNumber: partNumber, ETag: etag });
          uploadedSize += chunk.size;

          const progress = Math.round((uploadedSize / fileSize) * 100);
          if (progressCallback) {
            progressCallback(progress);
          }

          console.log(`分片 ${partNumber}/${totalChunks} 上传成功，进度: ${progress}%`);
          success = true;

        } catch (error) {
          retries++;
          console.warn(`分片 ${chunkIndex + 1} 上传失败，重试 ${retries}/${this.chunkConfig.maxRetries}:`, error);

          if (retries >= this.chunkConfig.maxRetries) {
            throw new Error(`分片上传失败: ${error instanceof Error ? error.message : '未知错误'}`);
          }

          // 等待一段时间后重试
          await this.delay(1000 * retries);
        }
      }
    }

    // 完成分片上传
    await this.completeMultipartUpload(fileKey, uploadId, uploadedParts);

    return {
      success: true,
      fileUrl: `${this.getPublicBaseUrl()}/${fileKey}`,
      fileKey,
      fileSize,
      uploadTime: Date.now()
    };
  }

  /**
   * 初始化分片上传
   */
  private async initMultipartUpload(fileKey: string): Promise<string> {
    const url = this.getUploadURL(fileKey) + '?uploads';
    const timestamp = Math.floor(Date.now() / 1000);
    const authorization = this.generateAuthorization('POST', fileKey, timestamp);

    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Authorization': authorization,
        'x-cos-timestamp': timestamp.toString()
      }
    });

    if (!response.ok) {
      throw new Error(`初始化分片上传失败: ${response.status}`);
    }

    const data = await response.text();

    // 简化XML解析，直接提取UploadId
    const uploadIdMatch = data.match(/<UploadId>([^<]+)<\/UploadId>/);
    if (!uploadIdMatch) {
      throw new Error('无法获取UploadId');
    }

    return uploadIdMatch[1];
  }

  /**
   * 上传分片
   */
  private async uploadPart(
    fileKey: string,
    uploadId: string,
    partNumber: number,
    chunk: Blob
  ): Promise<string> {
    const url = `${this.getUploadURL(fileKey)}?partNumber=${partNumber}&uploadId=${uploadId}`;
    const timestamp = Math.floor(Date.now() / 1000);
    const authorization = this.generateAuthorization('PUT', fileKey, timestamp);

    const response = await fetch(url, {
      method: 'PUT',
      body: chunk,
      headers: {
        'Authorization': authorization,
        'x-cos-timestamp': timestamp.toString(),
        'Content-Length': chunk.size.toString()
      }
    });

    if (!response.ok) {
      throw new Error(`分片上传失败: ${response.status}`);
    }

    const etag = response.headers.get('ETag');
    if (!etag) {
      throw new Error('无法获取ETag');
    }

    return etag;
  }

  /**
   * 完成分片上传
   */
  private async completeMultipartUpload(
    fileKey: string,
    uploadId: string,
    parts: Array<{ PartNumber: number; ETag: string }>
  ): Promise<void> {
    const url = this.getUploadURL(fileKey) + `?uploadId=${uploadId}`;
    const timestamp = Math.floor(Date.now() / 1000);

    // 构建XML请求体
    const completeRequest = `<?xml version="1.0" encoding="UTF-8"?>
      <CompleteMultipartUpload>
        ${parts.map(part => `
          <Part>
            <PartNumber>${part.PartNumber}</PartNumber>
            <ETag>${part.ETag}</ETag>
          </Part>
        `).join('')}
      </CompleteMultipartUpload>`;

    const authorization = this.generateAuthorization('POST', fileKey, timestamp);

    const response = await fetch(url, {
      method: 'POST',
      body: completeRequest,
      headers: {
        'Authorization': authorization,
        'x-cos-timestamp': timestamp.toString(),
        'Content-Type': 'application/xml'
      }
    });

    if (!response.ok) {
      throw new Error(`完成分片上传失败: ${response.status}`);
    }
  }

  /**
   * 生成文件存储键
   */
  private generateFileKey(fileName: string): string {
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const randomStr = Math.random().toString(36).substr(2, 8);

    // 提取策略类型（从文件名中）
    let strategyType = 'unknown';
    if (fileName.includes('均线')) strategyType = 'moving_average';
    else if (fileName.includes('动量')) strategyType = 'momentum';
    else if (fileName.includes('突破')) strategyType = 'breakout';
    else if (fileName.includes('套利')) strategyType = 'arbitrage';
    else if (fileName.includes('网格')) strategyType = 'grid';
    else strategyType = 'custom';

    return `strategies/${strategyType}/${timestamp}_${randomStr}_${fileName}`;
  }

  /**
   * 生成上传URL
   */
  private getUploadURL(fileKey: string): string {
    return `https://${this.config.bucket}.cos.${this.config.region}.myqcloud.com/${fileKey}`;
  }

  /**
   * 生成COS签名
   */
  private generateAuthorization(
    method: string,
    fileKey: string,
    timestamp: number
  ): string {
    // 简化的签名生成逻辑（实际使用时需要完整的COS签名算法）
    const signTime = `${timestamp};${timestamp + 3600}`;
    const keyTime = signTime;

    // 这里应该使用完整的COS签名算法
    // 由于签名算法较复杂，这里使用简化版本
    return `q-sign-algorithm=sha1&q-ak=${this.config.secretId}&q-sign-time=${signTime}&q-key-time=${keyTime}&q-header-list=&q-url-param-list=&q-signature=simplified_signature`;
  }

  /**
   * 获取文件大小
   */
  private getFileSize(content: string | Blob): number {
    if (typeof content === 'string') {
      return new Blob([content]).size;
    }
    return content.size;
  }

  /**
   * 格式化文件大小
   */
  private formatFileSize(bytes: number): string {
    if (bytes === 0) return '0 B';

    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));

    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  }

  /**
   * 延迟函数
   */
  private delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  /**
   * 验证配置是否有效
   */
  validateConfig(): boolean {
    return !!(this.config.secretId &&
              this.config.secretKey &&
              this.config.bucket &&
              this.config.region);
  }

  /**
   * 更新配置
   */
  updateConfig(newConfig: Partial<COSConfig>): void {
    this.config = { ...this.config, ...newConfig };
  }
}

import getStorageConfig from '../config/cosConfig';

// 创建全局上传服务实例
const storageConfig = getStorageConfig();
export const cosUploadService = new COSUploadService({
  secretId: '',
  secretKey: '',
  bucket: '',
  region: '',
  baseUrl: storageConfig.baseUrl,
});

export default COSUploadService;

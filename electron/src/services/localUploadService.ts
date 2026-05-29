/**
 * 本地文件上传服务 (OSS Edition)
 * 通过后端 API 上传文件到本地存储
 */

import { SERVICE_URLS } from '../config/services';

export interface UploadOptions {
  fileName: string;
  fileContent: string | Blob;
  fileType?: string;
  progressCallback?: (progress: number) => void;
  onSuccess?: (result: UploadResult) => void;
  onError?: (error: Error) => void;
}

export interface UploadResult {
  success: boolean;
  fileUrl: string;
  fileKey: string;
  fileSize: number;
  uploadTime: number;
  message?: string;
}

class LocalUploadService {
  private baseUrl: string;

  constructor(baseUrl?: string) {
    this.baseUrl = baseUrl || SERVICE_URLS.API_GATEWAY || '/api/v1';
  }

  private getApiBaseUrl(): string {
    return this.baseUrl;
  }

  /**
   * 上传文件到本地存储 (通过后端 API)
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
      console.log(`开始上传文件: ${fileName}`);

      if (progressCallback) {
        progressCallback(50);
      }

      const formData = new FormData();
      const blob = fileContent instanceof Blob 
        ? fileContent 
        : new Blob([fileContent], { type: fileType });
      formData.append('file', blob, fileName);

      const response = await fetch(`${this.getApiBaseUrl()}/files/upload`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Upload failed: ${response.statusText}`);
      }

      const result = await response.json();

      if (progressCallback) {
        progressCallback(100);
      }

      const uploadResult: UploadResult = {
        success: true,
        fileUrl: result.data?.file_url || result.file_url || '',
        fileKey: result.data?.file_key || result.file_key || fileName,
        fileSize: result.data?.file_size || result.file_size || blob.size,
        uploadTime: Date.now(),
      };

      if (onSuccess) {
        onSuccess(uploadResult);
      }

      console.log(`文件上传成功: ${uploadResult.fileUrl}`);
      return uploadResult;

    } catch (error) {
      const uploadResult: UploadResult = {
        success: false,
        fileUrl: '',
        fileKey: '',
        fileSize: 0,
        uploadTime: Date.now(),
        message: error instanceof Error ? error.message : 'Upload failed',
      };

      if (onError) {
        onError(error instanceof Error ? error : new Error('Upload failed'));
      }

      return uploadResult;
    }
  }

  /**
   * 上传大模型生成的JSON文件
   */
  async uploadModelOutputJson(
    jsonData: any,
    strategyType: string,
    timestamp: string
  ): Promise<UploadResult> {
    try {
      const fileName = `model_output_${strategyType}_${timestamp}.json`;
      const fileContent = JSON.stringify(jsonData, null, 2);

      return await this.uploadSimple(fileName, fileContent, 'application/json');
    } catch (error) {
      return {
        success: false,
        fileUrl: '',
        fileKey: '',
        fileSize: 0,
        uploadTime: Date.now(),
        message: `JSON上传失败: ${error instanceof Error ? error.message : '未知错误'}`,
      };
    }
  }

  /**
   * 上传解析后的Python文件
   */
  async uploadParsedPythonCode(
    pythonCode: string,
    strategyType: string,
    timestamp: string
  ): Promise<UploadResult> {
    try {
      const fileName = `parsed_code_${strategyType}_${timestamp}.py`;
      return await this.uploadSimple(fileName, pythonCode, 'text/x-python');
    } catch (error) {
      return {
        success: false,
        fileUrl: '',
        fileKey: '',
        fileSize: 0,
        uploadTime: Date.now(),
        message: `Python代码上传失败: ${error instanceof Error ? error.message : '未知错误'}`,
      };
    }
  }

  /**
   * 通用文件上传方法 (简化版)
   */
  async uploadSimple(
    fileName: string,
    content: string | Blob,
    contentType: string
  ): Promise<UploadResult> {
    return this.uploadFile({
      fileName,
      fileContent: content,
      fileType: contentType,
    });
  }

  /**
   * 获取文件URL
   */
  getFileUrl(fileKey: string): string {
    return `${this.getApiBaseUrl()}/files/${fileKey}`;
  }
}

export const localUploadService = new LocalUploadService();

export default localUploadService;

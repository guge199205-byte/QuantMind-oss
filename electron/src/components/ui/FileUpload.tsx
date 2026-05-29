import React, { useState, useCallback } from 'react';
import { Upload, X, FileText, Image, File, CheckCircle, AlertCircle } from 'lucide-react';
import { SERVICE_ENDPOINTS } from '../../config/services';

interface FileUploadProps {
  userId?: string;
  category?: 'auto' | 'image' | 'document' | 'archive';
  multiple?: boolean;
  accept?: string;
  maxFiles?: number;
  maxSize?: number; // MB
  description?: string;
  onUploadComplete?: (files: UploadedFile[]) => void;
  onUploadError?: (error: string) => void;
  disabled?: boolean;
}

interface UploadedFile {
  id: string;
  name: string;
  originalName: string;
  size: number;
  type: string;
  url: string;
  category: string;
  uploadTime: string;
}

export const FileUpload: React.FC<FileUploadProps> = ({
  userId = 'default_user',
  category = 'auto',
  multiple = false,
  accept,
  maxFiles = 5,
  maxSize = 50,
  description,
  onUploadComplete,
  onUploadError,
  disabled = false
}) => {
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<{ [key: string]: number }>({});
  const [dragOver, setDragOver] = useState(false);

  // 获取文件类型图标
  const getFileIcon = (type: string) => {
    if (type.startsWith('image/')) {
      return <Image className="w-4 h-4 text-green-500" />;
    } else if (type.includes('pdf') || type.includes('document') || type.includes('text')) {
      return <FileText className="w-4 h-4 text-blue-500" />;
    } else {
      return <File className="w-4 h-4 text-gray-500" />;
    }
  };

  // 格式化文件大小
  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  // 验证文件
  const validateFile = (file: File): string | null => {
    if (file.size > maxSize * 1024 * 1024) {
      return `文件大小超过限制 (${maxSize}MB)`;
    }

    if (accept && !accept.split(',').some(type => file.type.includes(type.trim()))) {
      return `不支持的文件类型: ${file.type}`;
    }

    return null;
  };

  // 上传单个文件
  const uploadSingleFile = async (file: File): Promise<UploadedFile | null> => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('user_id', userId);
    formData.append('category', category);
    formData.append('description', description || '');

    try {
      const response = await fetch(`${SERVICE_ENDPOINTS.API_GATEWAY}/files/upload`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.message || '上传失败');
      }

      const result = await response.json();

      if (result.code === 0) {
        return {
          id: result.data.file_id,
          name: result.data.file_name,
          originalName: result.data.original_name,
          size: result.data.file_size,
          type: result.data.content_type,
          url: result.data.file_url,
          category: result.data.file_category,
          uploadTime: result.data.upload_time
        };
      } else {
        throw new Error(result.message || '上传失败');
      }
    } catch (error) {
      console.error('文件上传失败:', error);
      throw error;
    }
  };

  // 处理文件选择
  const handleFileSelect = useCallback(async (selectedFiles: File[]) => {
    if (disabled || uploading) return;

    // 检查文件数量限制
    if (!multiple && selectedFiles.length > 1) {
      onUploadError?.('只能选择一个文件');
      return;
    }

    if (files.length + selectedFiles.length > maxFiles) {
      onUploadError?.(`最多只能上传 ${maxFiles} 个文件`);
      return;
    }

    // 验证文件
    const invalidFiles = selectedFiles.map(file => ({
      name: file.name,
      error: validateFile(file)
    })).filter(f => f.error);

    if (invalidFiles.length > 0) {
      onUploadError?.(invalidFiles.map(f => `${f.name}: ${f.error}`).join('\n'));
      return;
    }

    setUploading(true);
    const newUploadProgress: { [key: string]: number } = {};

    try {
      const uploadPromises = selectedFiles.map(async (file) => {
        newUploadProgress[file.name] = 0;
        setUploadProgress({ ...newUploadProgress });

        try {
          const uploadedFile = await uploadSingleFile(file);
          if (uploadedFile) {
            newUploadProgress[file.name] = 100;
            setUploadProgress({ ...newUploadProgress });
            return uploadedFile;
          }
          return null;
        } catch (error) {
          console.error(`上传文件 ${file.name} 失败:`, error);
          return null;
        }
      });

      const results = await Promise.all(uploadPromises);
      const successfulUploads = results.filter((f): f is UploadedFile => f !== null);

      if (successfulUploads.length > 0) {
        (setFiles as any)(prev => [...prev, ...successfulUploads]);
        onUploadComplete?.(successfulUploads);
      }

      const failedCount = selectedFiles.length - successfulUploads.length;
      if (failedCount > 0) {
        onUploadError?.(`${failedCount} 个文件上传失败`);
      }
    } catch (error) {
      onUploadError?.('上传过程中发生错误');
    } finally {
      setUploading(false);
      setUploadProgress({});
    }
  }, [disabled, uploading, files, multiple, maxFiles, category, description, onUploadComplete, onUploadError]);

  // 处理拖拽
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    if (!disabled && !uploading) {
      setDragOver(true);
    }
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);

    if (disabled || uploading) return;

    const droppedFiles = Array.from(e.dataTransfer.files);
    handleFileSelect(droppedFiles);
  };

  // 处理文件选择器
  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const selectedFiles = Array.from(e.target.files);
      handleFileSelect(selectedFiles);
    }
  };

  // 删除文件
  const removeFile = async (fileId: string) => {
    try {
      const file = files.find(f => f.id === fileId);
      if (file) {
        // 调用删除API
        await fetch(`${SERVICE_ENDPOINTS.API_GATEWAY}/files/delete`, {
          method: 'DELETE',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            file_key: file.id,
            user_id: userId
          }),
        });

        (setFiles as any)(prev => prev.filter(f => f.id !== fileId));
      }
    } catch (error) {
      console.error('删除文件失败:', error);
    }
  };

  return (
    <div className="space-y-4">
      {/* 上传区域 */}
      <div
        className={`relative border-2 border-dashed rounded-lg p-6 text-center transition-colors ${dragOver
            ? 'border-blue-500 bg-blue-50'
            : disabled
              ? 'border-gray-300 bg-gray-100 cursor-not-allowed'
              : 'border-gray-300 hover:border-gray-400 bg-white'
          }`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <input
          type="file"
          ref={(input) => {
            if (input && !disabled) {
              input.style.display = 'none';
              input.addEventListener('change', (e) => handleFileInputChange(e as any));
            }
          }}
          multiple={multiple}
          accept={accept}
          disabled={disabled || uploading}
        />

        <div className="flex flex-col items-center space-y-2">
          <Upload className={`w-8 h-8 ${uploading ? 'text-blue-500 animate-pulse' : 'text-gray-400'}`} />

          {uploading ? (
            <div className="text-sm text-blue-600">
              正在上传...
            </div>
          ) : (
            <>
              <div className="text-sm text-gray-600">
                拖拽文件到此处，或
                <button
                  className="ml-1 text-blue-600 hover:text-blue-700 underline"
                  onClick={() => {
                    const input = document.createElement('input');
                    input.type = 'file';
                    input.multiple = multiple;
                    input.accept = accept || '';
                    input.onchange = (e) => handleFileInputChange(e as any);
                    input.click();
                  }}
                  disabled={disabled}
                >
                  点击选择文件
                </button>
              </div>

              {description && (
                <div className="text-xs text-gray-500">{description}</div>
              )}

              {accept && (
                <div className="text-xs text-gray-400">
                  支持格式: {accept}
                </div>
              )}

              <div className="text-xs text-gray-400">
                最大文件大小: {maxSize}MB
                {multiple && ` | 最多 ${maxFiles} 个文件`}
              </div>
            </>
          )}
        </div>
      </div>

      {/* 上传进度 */}
      {uploading && Object.keys(uploadProgress).length > 0 && (
        <div className="space-y-2">
          {Object.entries(uploadProgress).map(([fileName, progress]) => (
            <div key={fileName} className="flex items-center space-x-2">
              <span className="text-sm text-gray-600 flex-1 truncate">{fileName}</span>
              <div className="flex items-center space-x-2">
                <div className="w-32 bg-gray-200 rounded-full h-2">
                  <div
                    className="bg-blue-500 h-2 rounded-full transition-all duration-300"
                    style={{ width: `${progress}%` }}
                  />
                </div>
                <span className="text-xs text-gray-500">{progress}%</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* 已上传文件列表 */}
      {files.length > 0 && (
        <div className="space-y-2">
          <div className="text-sm font-medium text-gray-700">
            已上传文件 ({files.length})
          </div>

          <div className="space-y-2">
            {files.map((file) => (
              <div
                key={file.id}
                className="flex items-center justify-between p-3 bg-white border border-gray-200 rounded-lg hover:bg-gray-50"
              >
                <div className="flex items-center space-x-3 flex-1 min-w-0">
                  {getFileIcon(file.type)}

                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-gray-900 truncate">
                      {file.originalName}
                    </div>
                    <div className="text-xs text-gray-500">
                      {formatFileSize(file.size)} • {file.category}
                    </div>
                  </div>

                  <CheckCircle className="w-4 h-4 text-green-500 flex-shrink-0" />
                </div>

                <div className="flex items-center space-x-2 ml-4">
                  <button
                    className="p-1 text-gray-400 hover:text-blue-600 transition-colors"
                    onClick={() => window.open(file.url, '_blank')}
                    title="查看文件"
                  >
                    <FileText className="w-4 h-4" />
                  </button>

                  <button
                    className="p-1 text-gray-400 hover:text-red-600 transition-colors"
                    onClick={() => removeFile(file.id)}
                    title="删除文件"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

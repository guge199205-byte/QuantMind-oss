import React, { useState, useCallback, useRef } from 'react';
import { Camera, Upload, X, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';
import { clsx } from 'clsx';
import { SERVICE_ENDPOINTS } from '../../config/services';

interface AvatarUploadProps {
  userId: string;
  currentAvatar?: string;
  onAvatarChange: (avatarUrl: string) => void;
  onError?: (error: string) => void;
  className?: string;
  disabled?: boolean;
}

interface UploadResponse {
  success: boolean;
  avatar_url: string;
  file_key: string;
  file_size: number;
  upload_time: string;
  message?: string;
}

interface AvatarSettings {
  allowed_types: string[];
  max_size_mb: number;
  max_size_bytes: number;
  recommended_dimensions: {
    width: number;
    height: number;
    aspect_ratio: string;
  };
  supported_formats: Record<string, { description: string; quality: string }>;
  upload_tips: string[];
}

export const AvatarUpload: React.FC<AvatarUploadProps> = ({
  userId,
  currentAvatar,
  onAvatarChange,
  onError,
  className,
  disabled = false
}) => {
  const [uploading, setUploading] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string>(currentAvatar || '');
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState<string>('');
  const [settings, setSettings] = useState<AvatarSettings | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const apiBase =
    ((import.meta as any).env?.VITE_USER_API_URL as string | undefined)?.replace(/\/+$/, '') ||
    SERVICE_ENDPOINTS.USER_SERVICE;

  // 获取头像上传设置
  React.useEffect(() => {
    const fetchSettings = async () => {
      try {
        const response = await fetch(`${apiBase}/avatar/settings`);
        if (response.ok) {
          const data = await response.json();
          setSettings(data.data);
        }
      } catch (err) {
        console.error('获取头像上传设置失败:', err);
      }
    };

    fetchSettings();
  }, []);

  // 验证文件
  const validateFile = useCallback((file: File): string | null => {
    if (!settings) return '上传设置未加载完成';

    // 检查文件类型
    const fileExt = file.name.split('.').pop()?.toLowerCase();
    if (!fileExt || !settings.allowed_types.includes(fileExt)) {
      return `不支持的文件类型。支持的格式: ${settings.allowed_types.join(', ')}`;
    }

    // 检查文件大小
    if (file.size > settings.max_size_bytes) {
      return `文件大小超过限制。最大大小: ${settings.max_size_mb}MB`;
    }

    return null;
  }, [settings]);

  // 创建预览
  const createPreview = useCallback((file: File): Promise<string> => {
    return new Promise((resolve) => {
      const reader = new FileReader();
      reader.onload = (e) => {
        resolve(e.target?.result as string);
      };
      reader.readAsDataURL(file);
    });
  }, []);

  // 上传头像
  const uploadAvatar = useCallback(async (file: File) => {
    if (disabled || uploading) return;

    const validationError = validateFile(file);
    if (validationError) {
      setError(validationError);
      onError?.(validationError);
      return;
    }

    setUploading(true);
    setError('');
    setUploadProgress(0);

    try {
      // 创建预览
      const preview = await createPreview(file);
      setPreviewUrl(preview);

      // 准备FormData
      const formData = new FormData();
      formData.append('file', file);
      formData.append('user_id', userId);

      // 创建XMLHttpRequest来支持进度监控
      const xhr = new XMLHttpRequest();

      return new Promise<void>((resolve, reject) => {
        // 监听上传进度
        xhr.upload.addEventListener('progress', (e) => {
          if (e.lengthComputable) {
            const progress = Math.round((e.loaded / e.total) * 100);
            setUploadProgress(progress);
          }
        });

        // 监听完成
        xhr.addEventListener('load', () => {
          if (xhr.status === 200) {
            try {
              const response: UploadResponse = JSON.parse(xhr.responseText);
              if (response.success) {
                setPreviewUrl(response.avatar_url);
                onAvatarChange(response.avatar_url);
                setError('');
              } else {
                const errorMsg = response.message || '上传失败';
                setError(errorMsg);
                onError?.(errorMsg);
                // 恢复原始头像
                setPreviewUrl(currentAvatar || '');
              }
            } catch (err) {
              const errorMsg = '响应解析失败';
              setError(errorMsg);
              onError?.(errorMsg);
              setPreviewUrl(currentAvatar || '');
            }
            resolve();
          } else {
            const errorMsg = `上传失败: HTTP ${xhr.status}`;
            setError(errorMsg);
            onError?.(errorMsg);
            setPreviewUrl(currentAvatar || '');
            reject(new Error(errorMsg));
          }
          setUploading(false);
          setUploadProgress(0);
        });

        // 监听错误
        xhr.addEventListener('error', () => {
          const errorMsg = '网络错误，上传失败';
          setError(errorMsg);
          onError?.(errorMsg);
          setPreviewUrl(currentAvatar || '');
          setUploading(false);
          setUploadProgress(0);
          reject(new Error(errorMsg));
        });

        // 发送请求
        xhr.open('POST', `${apiBase}/avatar/upload`);
        xhr.send(formData);
      });
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : '上传过程中发生错误';
      setError(errorMsg);
      onError?.(errorMsg);
      setPreviewUrl(currentAvatar || '');
      setUploading(false);
      setUploadProgress(0);
    }
  }, [userId, disabled, uploading, validateFile, createPreview, onAvatarChange, onError, currentAvatar]);

  // 处理文件选择
  const handleFileSelect = useCallback((file: File) => {
    uploadAvatar(file);
  }, [uploadAvatar]);

  // 处理拖拽
  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    if (!disabled && !uploading) {
      setDragOver(true);
    }
  }, [disabled, uploading]);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);

    if (disabled || uploading) return;

    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) {
      handleFileSelect(files[0]);
    }
  }, [disabled, uploading, handleFileSelect]);

  // 处理点击上传
  const handleClick = useCallback(() => {
    if (disabled || uploading) return;
    fileInputRef.current?.click();
  }, [disabled, uploading]);

  // 处理文件输入变化
  const handleFileInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      handleFileSelect(files[0]);
    }
  }, [handleFileSelect]);

  // 处理移除头像
  const handleRemoveAvatar = useCallback(() => {
    setPreviewUrl('');
    onAvatarChange('');
    setError('');
  }, [onAvatarChange]);

  return (
    <div className={clsx('avatar-upload', className)}>
      {/* 上传区域 */}
      <div
        className={clsx(
          'relative group cursor-pointer',
          'w-32 h-32 rounded-full overflow-hidden',
          'border-4 border-dashed transition-all duration-300',
          dragOver
            ? 'border-blue-500 bg-blue-50'
            : disabled
            ? 'border-gray-300 bg-gray-100 cursor-not-allowed'
            : 'border-gray-300 hover:border-gray-400 bg-white',
          uploading && 'pointer-events-none'
        )}
        onClick={handleClick}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        {/* 头像预览 */}
        {previewUrl ? (
          <img
            src={previewUrl}
            alt="用户头像"
            className="w-full h-full object-cover"
            onError={(e) => {
              e.currentTarget.src = '';
              setPreviewUrl('');
            }}
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center bg-gray-100">
            <Camera className="w-8 h-8 text-gray-400" />
          </div>
        )}

        {/* 上传状态遮罩 */}
        {uploading && (
          <div className="absolute inset-0 bg-black bg-opacity-50 flex items-center justify-center">
            <div className="text-center">
              <Loader2 className="w-8 h-8 text-white animate-spin mx-auto mb-2" />
              <div className="text-white text-sm">上传中...</div>
              <div className="text-white text-xs mt-1">{uploadProgress}%</div>
            </div>
          </div>
        )}

        {/* 悬停操作按钮 */}
        {!uploading && !disabled && (
          <div className="absolute inset-0 bg-black bg-opacity-0 group-hover:bg-opacity-50 transition-all duration-300 flex items-center justify-center opacity-0 group-hover:opacity-100">
            {previewUrl ? (
              <div className="flex space-x-2">
                <button
                  className="p-2 bg-white rounded-full shadow-lg hover:bg-gray-100 transition-colors"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleClick();
                  }}
                  title="更换头像"
                >
                  <Camera className="w-4 h-4 text-gray-700" />
                </button>
                <button
                  className="p-2 bg-white rounded-full shadow-lg hover:bg-red-100 transition-colors"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleRemoveAvatar();
                  }}
                  title="删除头像"
                >
                  <X className="w-4 h-4 text-red-600" />
                </button>
              </div>
            ) : (
              <div className="text-center">
                <Upload className="w-8 h-8 text-white mx-auto mb-2" />
                <div className="text-white text-sm">上传头像</div>
              </div>
            )}
          </div>
        )}

        {/* 进度条 */}
        {uploading && (
          <div className="absolute bottom-0 left-0 right-0 h-1 bg-gray-200">
            <div
              className="h-full bg-blue-500 transition-all duration-300"
              style={{ width: `${uploadProgress}%` }}
            />
          </div>
        )}
      </div>

      {/* 隐藏的文件输入 */}
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        onChange={handleFileInputChange}
        disabled={disabled || uploading}
        className="hidden"
      />

      {/* 错误提示 */}
      {error && (
        <div className="mt-2 flex items-center space-x-2 text-red-600">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          <span className="text-sm">{error}</span>
        </div>
      )}

      {/* 成功提示 */}
      {previewUrl && currentAvatar !== previewUrl && !uploading && !error && (
        <div className="mt-2 flex items-center space-x-2 text-green-600">
          <CheckCircle className="w-4 h-4 flex-shrink-0" />
          <span className="text-sm">头像更新成功</span>
        </div>
      )}

      {/* 上传提示 */}
      {settings && !previewUrl && !error && (
        <div className="mt-4 text-xs text-gray-500 space-y-1">
          <div>支持格式: {settings.allowed_types.join(', ')}</div>
          <div>最大大小: {settings.max_size_mb}MB</div>
          <div>推荐尺寸: {settings.recommended_dimensions.width}×{settings.recommended_dimensions.height}</div>
        </div>
      )}
    </div>
  );
};

export default AvatarUpload;

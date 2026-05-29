import React, { useEffect, useState } from 'react';
import { Progress } from 'antd';
import './ProgressBar.css';

/**
 * 进度条组件
 * 提供多种进度显示方式
 */

// 顶部加载进度条
export const TopProgressBar: React.FC<{
  loading?: boolean;
  color?: string;
}> = ({ loading = false, color = '#1890ff' }) => {
  const [percent, setPercent] = useState(0);

  useEffect(() => {
    if (loading) {
      setPercent(0);
      const timer = setInterval(() => {
        (setPercent as any)((prev) => {
          if (prev >= 90) {
            clearInterval(timer);
            return 90;
          }
          return prev + Math.random() * 10;
        });
      }, 200);

      return () => clearInterval(timer);
    } else {
      setPercent(100);
      const timer = setTimeout(() => {
        setPercent(0);
      }, 300);
      return () => clearTimeout(timer);
    }
  }, [loading]);

  if (percent === 0) return null;

  return (
    <div className="top-progress-bar">
      <Progress
        percent={percent}
        showInfo={false}
        strokeColor={color}
        status="active"
        style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          zIndex: 9999,
          margin: 0,
          padding: 0,
          height: 2
        }}
      />
    </div>
  );
};

// 圆形进度指示器
export const CircularProgress: React.FC<{
  percent: number;
  size?: number;
  status?: 'normal' | 'exception' | 'success';
  showInfo?: boolean;
}> = ({ percent, size = 120, status = 'normal', showInfo = true }) => {
  const getStatus = () => {
    if (status === 'exception') return 'exception';
    if (status === 'success' || percent === 100) return 'success';
    return 'active';
  };

  return (
    <div style={{ textAlign: 'center' }}>
      <Progress
        type="circle"
        percent={Math.round(percent)}
        status={getStatus()}
        width={size}
        format={(percent) => showInfo ? `${percent}%` : ''}
      />
    </div>
  );
};

// 步骤进度条
export const StepProgress: React.FC<{
  current: number;
  total: number;
  steps: string[];
}> = ({ current, total, steps }) => {
  const percent = Math.round((current / total) * 100);

  return (
    <div className="step-progress">
      <Progress percent={percent} status="active" />
      <div style={{ marginTop: 8, color: '#666', fontSize: 12 }}>
        {current < steps.length && (
          <div>当前步骤: {steps[current]}</div>
        )}
        <div>进度: {current}/{total}</div>
      </div>
    </div>
  );
};

// 多段进度条
export const MultiProgress: React.FC<{
  segments: Array<{
    label: string;
    percent: number;
    color: string;
  }>;
}> = ({ segments }) => {
  return (
    <div className="multi-progress">
      {segments.map((segment, index) => (
        <div key={index} style={{ marginBottom: 16 }}>
          <div style={{ marginBottom: 4, fontSize: 12, color: '#666' }}>
            {segment.label}
          </div>
          <Progress
            percent={segment.percent}
            strokeColor={segment.color}
            showInfo={true}
          />
        </div>
      ))}
    </div>
  );
};

// 带标签的进度条
export const LabeledProgress: React.FC<{
  label: string;
  percent: number;
  current?: number;
  total?: number;
  status?: 'normal' | 'exception' | 'success';
}> = ({ label, percent, current, total, status = 'normal' }) => {
  const getStatus = () => {
    if (status === 'exception') return 'exception';
    if (status === 'success' || percent === 100) return 'success';
    return 'active';
  };

  return (
    <div className="labeled-progress">
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        marginBottom: 8,
        fontSize: 14
      }}>
        <span>{label}</span>
        <span style={{ color: '#666' }}>
          {current !== undefined && total !== undefined
            ? `${current}/${total}`
            : `${Math.round(percent)}%`
          }
        </span>
      </div>
      <Progress
        percent={percent}
        status={getStatus()}
        showInfo={false}
      />
    </div>
  );
};

// 仪表盘进度
export const DashboardProgress: React.FC<{
  percent: number;
  title?: string;
  suffix?: string;
  color?: string;
}> = ({ percent, title, suffix = '%', color }) => {
  return (
    <div style={{ textAlign: 'center' }}>
      {title && (
        <div style={{ marginBottom: 16, fontSize: 16, fontWeight: 500 }}>
          {title}
        </div>
      )}
      <Progress
        type="dashboard"
        percent={Math.round(percent)}
        strokeColor={color}
        format={(percent) => `${percent}${suffix}`}
      />
    </div>
  );
};

// 加载占位进度条
export const LoadingProgress: React.FC<{
  loading?: boolean;
  message?: string;
  percent?: number;
}> = ({ loading = true, message = '加载中...', percent }) => {
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    if (loading && percent === undefined) {
      const timer = setInterval(() => {
        (setProgress as any)((prev) => {
          if (prev >= 95) return 95;
          return prev + Math.random() * 5;
        });
      }, 300);
      return () => clearInterval(timer);
    } else if (percent !== undefined) {
      setProgress(percent);
    }
  }, [loading, percent]);

  if (!loading) return null;

  return (
    <div style={{ padding: '40px 20px', textAlign: 'center' }}>
      <div style={{ maxWidth: 400, margin: '0 auto' }}>
        <CircularProgress percent={progress} size={80} />
        <div style={{ marginTop: 16, color: '#666' }}>
          {message}
        </div>
      </div>
    </div>
  );
};

// 全屏加载进度
export const FullscreenProgress: React.FC<{
  loading?: boolean;
  message?: string;
  percent?: number;
}> = ({ loading = true, message = '加载中...', percent }) => {
  if (!loading) return null;

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: 'rgba(255, 255, 255, 0.9)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 10000
      }}
    >
      <div style={{ textAlign: 'center' }}>
        <CircularProgress percent={percent || 50} size={100} />
        <div style={{ marginTop: 20, fontSize: 16, color: '#666' }}>
          {message}
        </div>
      </div>
    </div>
  );
};

export default {
  TopProgressBar,
  CircularProgress,
  StepProgress,
  MultiProgress,
  LabeledProgress,
  DashboardProgress,
  LoadingProgress,
  FullscreenProgress
};

/**
 * 图表标注工具栏
 * 提供各种标注工具
 */

import React, { useState } from 'react';

export type AnnotationTool =
  | 'none'
  | 'trendline'
  | 'horizontal'
  | 'vertical'
  | 'rectangle'
  | 'text'
  | 'marker'
  | 'fibonacci'
  | 'eraser';

export interface AnnotationToolbarProps {
  activeTool: AnnotationTool;
  onToolChange: (tool: AnnotationTool) => void;
  onUndo?: () => void;
  onRedo?: () => void;
  onClear?: () => void;
  canUndo?: boolean;
  canRedo?: boolean;
  className?: string;
}

interface ToolItem {
  id: AnnotationTool;
  name: string;
  icon: string;
  description: string;
  shortcut?: string;
}

const ANNOTATION_TOOLS: ToolItem[] = [
  {
    id: 'none',
    name: '选择',
    icon: '👆',
    description: '选择和移动标注',
    shortcut: 'V'
  },
  {
    id: 'trendline',
    name: '趋势线',
    icon: '📈',
    description: '绘制趋势线',
    shortcut: 'T'
  },
  {
    id: 'horizontal',
    name: '水平线',
    icon: '━',
    description: '绘制水平线',
    shortcut: 'H'
  },
  {
    id: 'vertical',
    name: '垂直线',
    icon: '┃',
    description: '绘制垂直线',
    shortcut: 'V'
  },
  {
    id: 'rectangle',
    name: '矩形',
    icon: '▭',
    description: '绘制矩形区域',
    shortcut: 'R'
  },
  {
    id: 'text',
    name: '文字',
    icon: '📝',
    description: '添加文字标注',
    shortcut: 'T'
  },
  {
    id: 'marker',
    name: '标记',
    icon: '🎯',
    description: '添加标记点',
    shortcut: 'M'
  },
  {
    id: 'fibonacci',
    name: '斐波那契',
    icon: '📐',
    description: '绘制斐波那契回调线',
    shortcut: 'F'
  },
  {
    id: 'eraser',
    name: '橡皮擦',
    icon: '🗑️',
    description: '删除标注',
    shortcut: 'E'
  }
];

/**
 * 标注工具栏组件
 */
export const AnnotationToolbar: React.FC<AnnotationToolbarProps> = ({
  activeTool,
  onToolChange,
  onUndo,
  onRedo,
  onClear,
  canUndo = false,
  canRedo = false,
  className = ''
}) => {
  const [hoveredTool, setHoveredTool] = useState<AnnotationTool | null>(null);

  const handleToolClick = (tool: AnnotationTool) => {
    onToolChange(tool);
  };

  const handleKeyPress = React.useCallback(
    (event: KeyboardEvent) => {
      // Ctrl/Cmd + Z: 撤销
      if ((event.ctrlKey || event.metaKey) && event.key === 'z' && !event.shiftKey) {
        event.preventDefault();
        onUndo?.();
      }
      // Ctrl/Cmd + Shift + Z: 重做
      else if ((event.ctrlKey || event.metaKey) && event.key === 'z' && event.shiftKey) {
        event.preventDefault();
        onRedo?.();
      }
      // Escape: 取消选择
      else if (event.key === 'Escape') {
        onToolChange('none');
      }
      // 工具快捷键
      else {
        const tool = ANNOTATION_TOOLS.find(
          t => t.shortcut && t.shortcut.toLowerCase() === event.key.toLowerCase()
        );
        if (tool) {
          onToolChange(tool.id);
        }
      }
    },
    [onToolChange, onUndo, onRedo]
  );

  React.useEffect(() => {
    window.addEventListener('keydown', handleKeyPress);
    return () => window.removeEventListener('keydown', handleKeyPress);
  }, [handleKeyPress]);

  return (
    <div className={`annotation-toolbar ${className}`}>
      {/* 工具按钮组 */}
      <div className="annotation-toolbar__tools">
        {ANNOTATION_TOOLS.map(tool => {
          const isActive = activeTool === tool.id;
          const isHovered = hoveredTool === tool.id;

          return (
            <button
              key={tool.id}
              className={`tool-button ${isActive ? 'tool-button--active' : ''} ${
                isHovered ? 'tool-button--hovered' : ''
              }`}
              onClick={() => handleToolClick(tool.id)}
              onMouseEnter={() => setHoveredTool(tool.id)}
              onMouseLeave={() => setHoveredTool(null)}
              title={`${tool.description}${tool.shortcut ? ` (${tool.shortcut})` : ''}`}
            >
              <span className="tool-button__icon">{tool.icon}</span>
              <span className="tool-button__name">{tool.name}</span>
              {tool.shortcut && (
                <span className="tool-button__shortcut">{tool.shortcut}</span>
              )}
            </button>
          );
        })}
      </div>

      {/* 操作按钮组 */}
      <div className="annotation-toolbar__actions">
        <button
          className="action-button"
          onClick={onUndo}
          disabled={!canUndo}
          title="撤销 (Ctrl+Z)"
        >
          ↶ 撤销
        </button>
        <button
          className="action-button"
          onClick={onRedo}
          disabled={!canRedo}
          title="重做 (Ctrl+Shift+Z)"
        >
          ↷ 重做
        </button>
        <button
          className="action-button action-button--danger"
          onClick={onClear}
          title="清除所有标注"
        >
          🗑️ 清除
        </button>
      </div>

      <style>{`
        .annotation-toolbar {
          display: flex;
          justify-content: space-between;
          align-items: center;
          gap: 16px;
          padding: 12px 16px;
          background: #ffffff;
          border-radius: 8px;
          box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        }

        .annotation-toolbar__tools {
          display: flex;
          gap: 4px;
          flex-wrap: wrap;
        }

        .tool-button {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 4px;
          padding: 8px 12px;
          background: transparent;
          border: 1px solid transparent;
          border-radius: 6px;
          cursor: pointer;
          transition: all 0.2s ease;
          min-width: 70px;
        }

        .tool-button:hover {
          background: #f9fafb;
          border-color: #e5e7eb;
        }

        .tool-button--active {
          background: #eff6ff;
          border-color: #3b82f6;
          box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.1);
        }

        .tool-button--hovered {
          transform: translateY(-2px);
          box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
        }

        .tool-button__icon {
          font-size: 20px;
        }

        .tool-button__name {
          font-size: 11px;
          font-weight: 500;
          color: #6b7280;
        }

        .tool-button--active .tool-button__name {
          color: #3b82f6;
          font-weight: 600;
        }

        .tool-button__shortcut {
          font-size: 9px;
          color: #9ca3af;
          background: #f3f4f6;
          padding: 1px 4px;
          border-radius: 3px;
          margin-top: 2px;
        }

        .annotation-toolbar__actions {
          display: flex;
          gap: 8px;
        }

        .action-button {
          padding: 8px 12px;
          font-size: 13px;
          font-weight: 500;
          color: #374151;
          background: #ffffff;
          border: 1px solid #d1d5db;
          border-radius: 6px;
          cursor: pointer;
          transition: all 0.2s ease;
        }

        .action-button:hover:not(:disabled) {
          background: #f9fafb;
          border-color: #9ca3af;
        }

        .action-button:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .action-button--danger {
          color: #dc2626;
          border-color: #fecaca;
        }

        .action-button--danger:hover:not(:disabled) {
          background: #fef2f2;
          border-color: #ef4444;
        }

        @media (max-width: 768px) {
          .annotation-toolbar {
            flex-direction: column;
            align-items: stretch;
          }

          .annotation-toolbar__tools {
            justify-content: center;
          }

          .annotation-toolbar__actions {
            justify-content: center;
          }
        }
      `}</style>
    </div>
  );
};

export default AnnotationToolbar;

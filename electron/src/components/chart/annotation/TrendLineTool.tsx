/**
 * 趋势线绘制工具
 * 支持绘制、编辑和删除趋势线
 */

import React, { useRef, useState, useEffect } from 'react';

export interface Point {
  x: number;
  y: number;
  price?: number;
  timestamp?: number;
}

export interface TrendLine {
  id: string;
  startPoint: Point;
  endPoint: Point;
  color: string;
  width: number;
  style: 'solid' | 'dashed' | 'dotted';
  extended: boolean; // 是否延伸
  label?: string;
}

export interface TrendLineToolProps {
  width: number;
  height: number;
  trendLines: TrendLine[];
  onAddTrendLine: (line: TrendLine) => void;
  onUpdateTrendLine: (id: string, line: Partial<TrendLine>) => void;
  onDeleteTrendLine: (id: string) => void;
  isActive: boolean;
  defaultColor?: string;
  defaultWidth?: number;
  className?: string;
}

/**
 * 趋势线工具组件
 */
export const TrendLineTool: React.FC<TrendLineToolProps> = ({
  width,
  height,
  trendLines,
  onAddTrendLine,
  onUpdateTrendLine,
  onDeleteTrendLine,
  isActive,
  defaultColor = '#3b82f6',
  defaultWidth = 2,
  className = ''
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [isDrawing, setIsDrawing] = useState(false);
  const [startPoint, setStartPoint] = useState<Point | null>(null);
  const [currentPoint, setCurrentPoint] = useState<Point | null>(null);
  const [selectedLineId, setSelectedLineId] = useState<string | null>(null);
  const [hoveredLineId, setHoveredLineId] = useState<string | null>(null);

  // 绘制所有趋势线
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // 清空画布
    ctx.clearRect(0, 0, width, height);

    // 绘制已有的趋势线
    trendLines.forEach(line => {
      const isSelected = line.id === selectedLineId;
      const isHovered = line.id === hoveredLineId;
      drawTrendLine(ctx, line, isSelected, isHovered);
    });

    // 绘制当前正在绘制的趋势线
    if (isDrawing && startPoint && currentPoint) {
      drawPreviewLine(ctx, startPoint, currentPoint);
    }
  }, [trendLines, isDrawing, startPoint, currentPoint, selectedLineId, hoveredLineId, width, height]);

  // 绘制趋势线
  const drawTrendLine = (
    ctx: CanvasRenderingContext2D,
    line: TrendLine,
    isSelected: boolean,
    isHovered: boolean
  ) => {
    ctx.save();

    // 设置样式
    ctx.strokeStyle = line.color;
    ctx.lineWidth = isSelected ? line.width + 2 : isHovered ? line.width + 1 : line.width;
    ctx.globalAlpha = isSelected || isHovered ? 1 : 0.8;

    // 设置线条样式
    if (line.style === 'dashed') {
      ctx.setLineDash([10, 5]);
    } else if (line.style === 'dotted') {
      ctx.setLineDash([2, 3]);
    }

    // 绘制线条
    ctx.beginPath();
    ctx.moveTo(line.startPoint.x, line.startPoint.y);
    ctx.lineTo(line.endPoint.x, line.endPoint.y);
    ctx.stroke();

    // 如果延伸，绘制延伸线
    if (line.extended) {
      ctx.setLineDash([5, 5]);
      ctx.globalAlpha = 0.4;

      // 计算延伸方向
      const dx = line.endPoint.x - line.startPoint.x;
      const dy = line.endPoint.y - line.startPoint.y;
      const length = Math.sqrt(dx * dx + dy * dy);
      const extendFactor = 2;

      ctx.beginPath();
      ctx.moveTo(line.endPoint.x, line.endPoint.y);
      ctx.lineTo(
        line.endPoint.x + (dx / length) * width * extendFactor,
        line.endPoint.y + (dy / length) * height * extendFactor
      );
      ctx.stroke();
    }

    // 绘制端点
    if (isSelected) {
      drawHandle(ctx, line.startPoint.x, line.startPoint.y, line.color);
      drawHandle(ctx, line.endPoint.x, line.endPoint.y, line.color);
    }

    // 绘制标签
    if (line.label) {
      const midX = (line.startPoint.x + line.endPoint.x) / 2;
      const midY = (line.startPoint.y + line.endPoint.y) / 2;
      drawLabel(ctx, midX, midY, line.label, line.color);
    }

    ctx.restore();
  };

  // 绘制预览线
  const drawPreviewLine = (ctx: CanvasRenderingContext2D, start: Point, end: Point) => {
    ctx.save();
    ctx.strokeStyle = defaultColor;
    ctx.lineWidth = defaultWidth;
    ctx.setLineDash([5, 5]);
    ctx.globalAlpha = 0.6;

    ctx.beginPath();
    ctx.moveTo(start.x, start.y);
    ctx.lineTo(end.x, end.y);
    ctx.stroke();

    ctx.restore();
  };

  // 绘制控制点
  const drawHandle = (ctx: CanvasRenderingContext2D, x: number, y: number, color: string) => {
    ctx.save();
    ctx.fillStyle = color;
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 2;

    ctx.beginPath();
    ctx.arc(x, y, 5, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();

    ctx.restore();
  };

  // 绘制标签
  const drawLabel = (ctx: CanvasRenderingContext2D, x: number, y: number, text: string, color: string) => {
    ctx.save();
    ctx.font = '12px sans-serif';
    ctx.fillStyle = color;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'bottom';

    // 绘制背景
    const metrics = ctx.measureText(text);
    const padding = 4;
    ctx.fillStyle = 'rgba(255, 255, 255, 0.9)';
    ctx.fillRect(
      x - metrics.width / 2 - padding,
      y - 16 - padding,
      metrics.width + padding * 2,
      16 + padding * 2
    );

    // 绘制文字
    ctx.fillStyle = color;
    ctx.fillText(text, x, y);

    ctx.restore();
  };

  // 处理鼠标按下
  const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!isActive) return;

    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const point: Point = { x, y };

    // 检查是否点击了已有的趋势线
    const clickedLine = findLineAtPoint(point);
    if (clickedLine) {
      setSelectedLineId(clickedLine.id);
      return;
    }

    // 开始绘制新趋势线
    setIsDrawing(true);
    setStartPoint(point);
    setCurrentPoint(point);
    setSelectedLineId(null);
  };

  // 处理鼠标移动
  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const point: Point = { x, y };

    if (isDrawing) {
      setCurrentPoint(point);
    } else {
      // 检查悬停
      const hoveredLine = findLineAtPoint(point);
      setHoveredLineId(hoveredLine?.id || null);
    }
  };

  // 处理鼠标抬起
  const handleMouseUp = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!isDrawing || !startPoint || !currentPoint) return;

    // 创建新趋势线
    const newLine: TrendLine = {
      id: `trendline-${Date.now()}`,
      startPoint,
      endPoint: currentPoint,
      color: defaultColor,
      width: defaultWidth,
      style: 'solid',
      extended: false
    };

    onAddTrendLine(newLine);

    // 重置状态
    setIsDrawing(false);
    setStartPoint(null);
    setCurrentPoint(null);
  };

  // 查找点击位置的趋势线
  const findLineAtPoint = (point: Point, threshold: number = 5): TrendLine | null => {
    for (const line of trendLines) {
      const distance = pointToLineDistance(
        point,
        line.startPoint,
        line.endPoint
      );
      if (distance <= threshold) {
        return line;
      }
    }
    return null;
  };

  // 计算点到线段的距离
  const pointToLineDistance = (point: Point, lineStart: Point, lineEnd: Point): number => {
    const { x, y } = point;
    const { x: x1, y: y1 } = lineStart;
    const { x: x2, y: y2 } = lineEnd;

    const A = x - x1;
    const B = y - y1;
    const C = x2 - x1;
    const D = y2 - y1;

    const dot = A * C + B * D;
    const lenSq = C * C + D * D;
    let param = -1;

    if (lenSq !== 0) {
      param = dot / lenSq;
    }

    let xx, yy;

    if (param < 0) {
      xx = x1;
      yy = y1;
    } else if (param > 1) {
      xx = x2;
      yy = y2;
    } else {
      xx = x1 + param * C;
      yy = y1 + param * D;
    }

    const dx = x - xx;
    const dy = y - yy;
    return Math.sqrt(dx * dx + dy * dy);
  };

  // 处理键盘事件
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Delete' && selectedLineId) {
        onDeleteTrendLine(selectedLineId);
        setSelectedLineId(null);
      } else if (e.key === 'Escape') {
        setSelectedLineId(null);
        setIsDrawing(false);
        setStartPoint(null);
        setCurrentPoint(null);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [selectedLineId, onDeleteTrendLine]);

  return (
    <div className={`trendline-tool ${className}`}>
      <canvas
        ref={canvasRef}
        width={width}
        height={height}
        className="trendline-tool__canvas"
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        style={{ cursor: isActive ? 'crosshair' : 'default' }}
      />

      {selectedLineId && (
        <div className="trendline-tool__controls">
          <button
            className="control-button"
            onClick={() => {
              const line = trendLines.find(l => l.id === selectedLineId);
              if (line) {
                onUpdateTrendLine(selectedLineId, { extended: !line.extended });
              }
            }}
          >
            {trendLines.find(l => l.id === selectedLineId)?.extended ? '取消延伸' : '延伸线'}
          </button>
          <button
            className="control-button control-button--danger"
            onClick={() => {
              onDeleteTrendLine(selectedLineId);
              setSelectedLineId(null);
            }}
          >
            删除
          </button>
        </div>
      )}

      <style>{`
        .trendline-tool {
          position: relative;
        }

        .trendline-tool__canvas {
          display: block;
        }

        .trendline-tool__controls {
          position: absolute;
          top: 10px;
          right: 10px;
          display: flex;
          gap: 8px;
          padding: 8px;
          background: rgba(255, 255, 255, 0.9);
          border-radius: 6px;
          box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        }

        .control-button {
          padding: 6px 12px;
          font-size: 12px;
          font-weight: 500;
          color: #374151;
          background: #ffffff;
          border: 1px solid #d1d5db;
          border-radius: 4px;
          cursor: pointer;
          transition: all 0.2s ease;
        }

        .control-button:hover {
          background: #f9fafb;
          border-color: #9ca3af;
        }

        .control-button--danger {
          color: #dc2626;
          border-color: #fecaca;
        }

        .control-button--danger:hover {
          background: #fef2f2;
          border-color: #ef4444;
        }
      `}</style>
    </div>
  );
};

export default TrendLineTool;

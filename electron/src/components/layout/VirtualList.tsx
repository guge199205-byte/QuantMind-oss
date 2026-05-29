import React, { useRef, useState, useEffect, useCallback, CSSProperties } from 'react';

/**
 * 虚拟列表组件
 * 用于高性能渲染大量列表项
 */

interface VirtualListProps<T> {
  data: T[];
  itemHeight: number | ((item: T, index: number) => number);
  renderItem: (item: T, index: number) => React.ReactNode;
  height: number;
  overscan?: number;
  className?: string;
  style?: CSSProperties;
  onScroll?: (scrollTop: number) => void;
}

export function VirtualList<T>({
  data,
  itemHeight,
  renderItem,
  height,
  overscan = 3,
  className = '',
  style = {},
  onScroll
}: VirtualListProps<T>) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [scrollTop, setScrollTop] = useState(0);

  // 计算单个项目的高度
  const getItemHeight = useCallback((item: T, index: number): number => {
    return typeof itemHeight === 'function' ? itemHeight(item, index) : itemHeight;
  }, [itemHeight]);

  // 计算总高度
  const totalHeight = data.reduce((acc, item, index) => {
    return acc + getItemHeight(item, index);
  }, 0);

  // 计算可见范围
  const getVisibleRange = useCallback(() => {
    let startIndex = 0;
    let endIndex = 0;
    let accumulatedHeight = 0;

    // 找到起始索引
    for (let i = 0; i < data.length; i++) {
      const height = getItemHeight(data[i], i);
      if (accumulatedHeight + height > scrollTop) {
        startIndex = Math.max(0, i - overscan);
        break;
      }
      accumulatedHeight += height;
    }

    // 找到结束索引
    accumulatedHeight = 0;
    for (let i = 0; i < data.length; i++) {
      const itemHeight = getItemHeight(data[i], i);
      accumulatedHeight += itemHeight;
      if (accumulatedHeight >= scrollTop + height) {
        endIndex = Math.min(data.length - 1, i + overscan);
        break;
      }
    }

    if (endIndex === 0) {
      endIndex = data.length - 1;
    }

    return { startIndex, endIndex };
  }, [data, height, scrollTop, overscan, getItemHeight]);

  // 计算偏移量
  const getOffsetTop = useCallback((index: number): number => {
    let offset = 0;
    for (let i = 0; i < index; i++) {
      offset += getItemHeight(data[i], i);
    }
    return offset;
  }, [data, getItemHeight]);

  const { startIndex, endIndex } = getVisibleRange();
  const visibleItems = data.slice(startIndex, endIndex + 1);
  const offsetTop = getOffsetTop(startIndex);

  const handleScroll = useCallback((e: React.UIEvent<HTMLDivElement>) => {
    const newScrollTop = e.currentTarget.scrollTop;
    setScrollTop(newScrollTop);
    if (onScroll) {
      onScroll(newScrollTop);
    }
  }, [onScroll]);

  return (
    <div
      ref={containerRef}
      className={`virtual-list ${className}`}
      style={{
        height,
        overflow: 'auto',
        position: 'relative',
        ...style
      }}
      onScroll={handleScroll}
    >
      <div style={{ height: totalHeight, position: 'relative' }}>
        <div
          style={{
            position: 'absolute',
            top: offsetTop,
            left: 0,
            right: 0
          }}
        >
          {visibleItems.map((item, relativeIndex) => {
            const actualIndex = startIndex + relativeIndex;
            return (
              <div
                key={actualIndex}
                style={{
                  height: getItemHeight(item, actualIndex)
                }}
              >
                {renderItem(item, actualIndex)}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// 固定高度虚拟列表（优化版）
export const FixedHeightVirtualList: React.FC<{
  data: any[];
  itemHeight: number;
  renderItem: (item: any, index: number) => React.ReactNode;
  height: number;
  width?: string | number;
  overscan?: number;
  className?: string;
}> = ({
  data,
  itemHeight,
  renderItem,
  height,
  width = '100%',
  overscan = 3,
  className = ''
}) => {
  const [scrollTop, setScrollTop] = useState(0);

  const totalHeight = data.length * itemHeight;
  const startIndex = Math.max(0, Math.floor(scrollTop / itemHeight) - overscan);
  const endIndex = Math.min(
    data.length - 1,
    Math.ceil((scrollTop + height) / itemHeight) + overscan
  );

  const visibleItems = data.slice(startIndex, endIndex + 1);
  const offsetTop = startIndex * itemHeight;

  const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
    setScrollTop(e.currentTarget.scrollTop);
  };

  return (
    <div
      className={`fixed-virtual-list ${className}`}
      style={{
        height,
        width,
        overflow: 'auto',
        position: 'relative'
      }}
      onScroll={handleScroll}
    >
      <div style={{ height: totalHeight, position: 'relative' }}>
        <div
          style={{
            position: 'absolute',
            top: offsetTop,
            left: 0,
            right: 0
          }}
        >
          {visibleItems.map((item, relativeIndex) => {
            const actualIndex = startIndex + relativeIndex;
            return (
              <div
                key={actualIndex}
                style={{ height: itemHeight }}
              >
                {renderItem(item, actualIndex)}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

// 网格虚拟列表
export const VirtualGrid: React.FC<{
  data: any[];
  itemHeight: number;
  itemWidth: number;
  columns: number;
  renderItem: (item: any, index: number) => React.ReactNode;
  height: number;
  gap?: number;
  className?: string;
}> = ({
  data,
  itemHeight,
  itemWidth,
  columns,
  renderItem,
  height,
  gap = 16,
  className = ''
}) => {
  const [scrollTop, setScrollTop] = useState(0);

  const rowHeight = itemHeight + gap;
  const rows = Math.ceil(data.length / columns);
  const totalHeight = rows * rowHeight;

  const startRow = Math.max(0, Math.floor(scrollTop / rowHeight) - 1);
  const endRow = Math.min(rows - 1, Math.ceil((scrollTop + height) / rowHeight) + 1);

  const visibleData: any[] = [];
  for (let row = startRow; row <= endRow; row++) {
    for (let col = 0; col < columns; col++) {
      const index = row * columns + col;
      if (index < data.length) {
        visibleData.push({ item: data[index], row, col, index });
      }
    }
  }

  const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
    setScrollTop(e.currentTarget.scrollTop);
  };

  return (
    <div
      className={`virtual-grid ${className}`}
      style={{
        height,
        overflow: 'auto',
        position: 'relative'
      }}
      onScroll={handleScroll}
    >
      <div style={{ height: totalHeight, position: 'relative' }}>
        {visibleData.map(({ item, row, col, index }) => (
          <div
            key={index}
            style={{
              position: 'absolute',
              top: row * rowHeight,
              left: col * (itemWidth + gap),
              width: itemWidth,
              height: itemHeight
            }}
          >
            {renderItem(item, index)}
          </div>
        ))}
      </div>
    </div>
  );
};

// 使用Intersection Observer的虚拟列表
export const IntersectionVirtualList: React.FC<{
  data: any[];
  renderItem: (item: any, index: number) => React.ReactNode;
  threshold?: number;
  rootMargin?: string;
  className?: string;
}> = ({
  data,
  renderItem,
  threshold = 0.1,
  rootMargin = '100px',
  className = ''
}) => {
  const [visibleIndices, setVisibleIndices] = useState<Set<number>>(new Set());
  const observerRef = useRef<IntersectionObserver | null>(null);
  const itemRefs = useRef<Map<number, HTMLDivElement>>(new Map());

  useEffect(() => {
    observerRef.current = new IntersectionObserver(
      (entries) => {
        (setVisibleIndices as any)((prev) => {
          const newSet = new Set(prev);
          entries.forEach((entry) => {
            const index = parseInt(entry.target.getAttribute('data-index') || '0', 10);
            if (entry.isIntersecting) {
              newSet.add(index);
            } else {
              newSet.delete(index);
            }
          });
          return newSet;
        });
      },
      {
        threshold,
        rootMargin
      }
    );

    return () => {
      observerRef.current?.disconnect();
    };
  }, [threshold, rootMargin]);

  const setItemRef = useCallback((index: number) => (element: HTMLDivElement | null) => {
    if (element) {
      itemRefs.current.set(index, element);
      observerRef.current?.observe(element);
    } else {
      const oldElement = itemRefs.current.get(index);
      if (oldElement) {
        observerRef.current?.unobserve(oldElement);
        itemRefs.current.delete(index);
      }
    }
  }, []);

  return (
    <div className={`intersection-virtual-list ${className}`}>
      {data.map((item, index) => (
        <div
          key={index}
          ref={setItemRef(index)}
          data-index={index}
          style={{ minHeight: 50 }}
        >
          {visibleIndices.has(index) ? renderItem(item, index) : <div style={{ height: 50 }} />}
        </div>
      ))}
    </div>
  );
};

export default VirtualList;

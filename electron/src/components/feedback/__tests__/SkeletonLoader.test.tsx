import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import {
  TableSkeleton,
  ChartSkeleton,
  CardSkeleton,
  ListSkeleton,
  SkeletonWrapper
} from '../SkeletonLoader';

describe('SkeletonLoader Components', () => {
  describe('TableSkeleton', () => {
    it('应该渲染表格骨架屏', () => {
      const { container } = render(<TableSkeleton rows={5} />);
      expect(container.querySelector('.table-skeleton')).toBeTruthy();
    });

    it('应该渲染指定数量的行', () => {
      const { container } = render(<TableSkeleton rows={5} />);
      const rows = container.querySelectorAll('.ant-row');
      expect(rows.length).toBeGreaterThan(0);
    });

    it('加载完成后应该显示子元素', () => {
      const { container } = render(
        <TableSkeleton loading={false}>
          <div data-testid="content">Content</div>
        </TableSkeleton>
      );
      expect(screen.getByTestId('content')).toBeTruthy();
      expect(container.querySelector('.table-skeleton')).toBeFalsy();
    });

    it('应该使用默认行数', () => {
      const { container } = render(<TableSkeleton />);
      expect(container.querySelector('.table-skeleton')).toBeTruthy();
    });
  });

  describe('ChartSkeleton', () => {
    it('应该渲染图表骨架屏', () => {
      const { container } = render(<ChartSkeleton height={400} />);
      expect(container.querySelector('.ant-card')).toBeTruthy();
    });

    it('应该使用自定义高度', () => {
      const customHeight = 300;
      const { container } = render(<ChartSkeleton height={customHeight} />);
      const skeleton = container.querySelector('.ant-skeleton-element');
      expect(skeleton).toBeTruthy();
    });

    it('加载完成后应该显示子元素', () => {
      const { container } = render(
        <ChartSkeleton loading={false}>
          <div data-testid="chart">Chart</div>
        </ChartSkeleton>
      );
      expect(screen.getByTestId('chart')).toBeTruthy();
    });

    it('应该使用默认高度', () => {
      const { container } = render(<ChartSkeleton />);
      expect(container.querySelector('.ant-card')).toBeTruthy();
    });
  });

  describe('CardSkeleton', () => {
    it('应该渲染卡片骨架屏', () => {
      const { container } = render(<CardSkeleton />);
      expect(container.querySelector('.ant-card')).toBeTruthy();
      expect(container.querySelector('.ant-skeleton')).toBeTruthy();
    });

    it('加载完成后应该显示子元素', () => {
      const { container } = render(
        <CardSkeleton loading={false}>
          <div data-testid="card-content">Card Content</div>
        </CardSkeleton>
      );
      expect(screen.getByTestId('card-content')).toBeTruthy();
      expect(container.querySelector('.ant-skeleton')).toBeFalsy();
    });
  });

  describe('ListSkeleton', () => {
    it('应该渲染列表骨架屏', () => {
      const { container } = render(<ListSkeleton items={3} />);
      expect(container.querySelector('.list-skeleton')).toBeTruthy();
    });

    it('应该渲染指定数量的项', () => {
      const itemCount = 5;
      const { container } = render(<ListSkeleton items={itemCount} />);
      const cards = container.querySelectorAll('.ant-card');
      expect(cards.length).toBe(itemCount);
    });

    it('加载完成后应该显示子元素', () => {
      const { container } = render(
        <ListSkeleton loading={false}>
          <div data-testid="list-content">List Content</div>
        </ListSkeleton>
      );
      expect(screen.getByTestId('list-content')).toBeTruthy();
      expect(container.querySelector('.list-skeleton')).toBeFalsy();
    });

    it('应该使用默认项数', () => {
      const { container } = render(<ListSkeleton />);
      const cards = container.querySelectorAll('.ant-card');
      expect(cards.length).toBe(5);
    });
  });

  describe('SkeletonWrapper', () => {
    it('应该根据type渲染不同类型', () => {
      const { container: tableContainer } = render(
        <SkeletonWrapper loading={true} type="table" />
      );
      expect(tableContainer.querySelector('.table-skeleton')).toBeTruthy();

      const { container: chartContainer } = render(
        <SkeletonWrapper loading={true} type="chart" />
      );
      expect(chartContainer.querySelector('.ant-card')).toBeTruthy();

      const { container: listContainer } = render(
        <SkeletonWrapper loading={true} type="list" />
      );
      expect(listContainer.querySelector('.list-skeleton')).toBeTruthy();
    });

    it('加载完成后应该显示子元素', () => {
      const { container } = render(
        <SkeletonWrapper loading={false} type="card">
          <div data-testid="wrapper-content">Content</div>
        </SkeletonWrapper>
      );
      expect(screen.getByTestId('wrapper-content')).toBeTruthy();
    });

    it('应该传递参数给子组件', () => {
      const { container } = render(
        <SkeletonWrapper loading={true} type="table" rows={10} />
      );
      expect(container.querySelector('.table-skeleton')).toBeTruthy();
    });
  });
});

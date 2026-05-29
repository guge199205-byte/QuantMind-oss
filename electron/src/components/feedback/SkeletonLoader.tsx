import React from 'react';
import { Skeleton, Card, Row, Col } from 'antd';

/**
 * Skeleton加载组件
 * 提供多种加载占位符效果
 */

interface SkeletonLoaderProps {
  loading?: boolean;
  children?: React.ReactNode;
}

// 表格Skeleton
export const TableSkeleton: React.FC<{ rows?: number } & SkeletonLoaderProps> = ({
  rows = 10,
  loading = true,
  children
}) => {
  if (!loading && children) {
    return <>{children}</>;
  }

  return (
    <div className="table-skeleton">
      {/* 表头 */}
      <div style={{ marginBottom: 16 }}>
        <Skeleton.Input active style={{ width: '100%', height: 40 }} block />
      </div>

      {/* 表格行 */}
      {Array.from({ length: rows }).map((_, index) => (
        <div key={index} style={{ marginBottom: 8 }}>
          <Row gutter={16}>
            <Col span={4}>
              <Skeleton.Input active style={{ width: '100%' }} />
            </Col>
            <Col span={4}>
              <Skeleton.Input active style={{ width: '100%' }} />
            </Col>
            <Col span={4}>
              <Skeleton.Input active style={{ width: '100%' }} />
            </Col>
            <Col span={4}>
              <Skeleton.Input active style={{ width: '100%' }} />
            </Col>
            <Col span={4}>
              <Skeleton.Input active style={{ width: '100%' }} />
            </Col>
            <Col span={4}>
              <Skeleton.Input active style={{ width: '100%' }} />
            </Col>
          </Row>
        </div>
      ))}
    </div>
  );
};

// 图表Skeleton
export const ChartSkeleton: React.FC<{ height?: number } & SkeletonLoaderProps> = ({
  height = 400,
  loading = true,
  children
}) => {
  if (!loading && children) {
    return <>{children}</>;
  }

  return (
    <Card>
      <div style={{ marginBottom: 16 }}>
        <Skeleton.Input active style={{ width: 200 }} />
      </div>
      <Skeleton.Node active style={{ width: '100%', height }}>
        <div style={{ width: '100%', height }} />
      </Skeleton.Node>
      <div style={{ marginTop: 16 }}>
        <Row gutter={16}>
          <Col span={6}>
            <Skeleton.Input active style={{ width: '100%' }} />
          </Col>
          <Col span={6}>
            <Skeleton.Input active style={{ width: '100%' }} />
          </Col>
          <Col span={6}>
            <Skeleton.Input active style={{ width: '100%' }} />
          </Col>
          <Col span={6}>
            <Skeleton.Input active style={{ width: '100%' }} />
          </Col>
        </Row>
      </div>
    </Card>
  );
};

// 卡片Skeleton
export const CardSkeleton: React.FC<SkeletonLoaderProps> = ({
  loading = true,
  children
}) => {
  if (!loading && children) {
    return <>{children}</>;
  }

  return (
    <Card>
      <Skeleton active paragraph={{ rows: 4 }} />
    </Card>
  );
};

// 列表Skeleton
export const ListSkeleton: React.FC<{ items?: number } & SkeletonLoaderProps> = ({
  items = 5,
  loading = true,
  children
}) => {
  if (!loading && children) {
    return <>{children}</>;
  }

  return (
    <div className="list-skeleton">
      {Array.from({ length: items }).map((_, index) => (
        <Card key={index} style={{ marginBottom: 16 }}>
          <Skeleton active avatar paragraph={{ rows: 2 }} />
        </Card>
      ))}
    </div>
  );
};

// 仪表板Skeleton（组合多个Skeleton）
export const DashboardSkeleton: React.FC = () => {
  return (
    <div>
      <Row gutter={[16, 16]}>
        <Col span={6}>
          <CardSkeleton />
        </Col>
        <Col span={6}>
          <CardSkeleton />
        </Col>
        <Col span={6}>
          <CardSkeleton />
        </Col>
        <Col span={6}>
          <CardSkeleton />
        </Col>
      </Row>
      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col span={16}>
          <ChartSkeleton height={300} />
        </Col>
        <Col span={8}>
          <ListSkeleton items={3} />
        </Col>
      </Row>
    </div>
  );
};

// 详情页Skeleton
export const DetailSkeleton: React.FC = () => {
  return (
    <div>
      <Card style={{ marginBottom: 16 }}>
        <Skeleton active paragraph={{ rows: 1 }} />
      </Card>
      <Row gutter={[16, 16]}>
        <Col span={24}>
          <ChartSkeleton height={350} />
        </Col>
      </Row>
      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col span={12}>
          <CardSkeleton />
        </Col>
        <Col span={12}>
          <CardSkeleton />
        </Col>
      </Row>
    </div>
  );
};

// 通用Skeleton包装器
export const SkeletonWrapper: React.FC<{
  loading: boolean;
  type?: 'table' | 'chart' | 'card' | 'list' | 'dashboard' | 'detail';
  rows?: number;
  items?: number;
  height?: number;
  children?: React.ReactNode;
}> = ({
  loading,
  type = 'card',
  rows,
  items,
  height,
  children
}) => {
  if (!loading && children) {
    return <>{children}</>;
  }

  switch (type) {
    case 'table':
      return <TableSkeleton rows={rows} loading={loading} />;
    case 'chart':
      return <ChartSkeleton height={height} loading={loading} />;
    case 'list':
      return <ListSkeleton items={items} loading={loading} />;
    case 'dashboard':
      return <DashboardSkeleton />;
    case 'detail':
      return <DetailSkeleton />;
    case 'card':
    default:
      return <CardSkeleton loading={loading} />;
  }
};

export default SkeletonWrapper;

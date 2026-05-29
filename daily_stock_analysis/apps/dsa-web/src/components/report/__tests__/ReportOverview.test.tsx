import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ReportOverview } from '../ReportOverview';

const baseMeta = {
  queryId: 'q-1',
  stockCode: '600519',
  stockName: '贵州茅台',
  reportType: 'detailed' as const,
  reportLanguage: 'zh' as const,
  createdAt: '2026-03-21T08:00:00Z',
};

const baseSummary = {
  analysisSummary: '趋势维持强势',
  operationAdvice: '继续观察买点',
  trendPrediction: '短线震荡偏强',
  sentimentScore: 78,
};

describe('ReportOverview', () => {
  it('renders related boards with leading and lagging markers', () => {
    render(
      <ReportOverview
        meta={baseMeta}
        summary={baseSummary}
        details={{
          belongBoards: [
            { name: ' 白酒 ', type: '行业' },
            { name: '消费', type: '概念' },
            { name: '新能源' },
          ],
          sectorRankings: {
            top: [{ name: '白酒', changePct: 2.31 }],
            bottom: [{ name: '消费', changePct: -1.2 }],
          },
        }}
      />,
    );

    expect(screen.getByText('关联板块')).toBeInTheDocument();
    expect(screen.getByText('白酒')).toBeInTheDocument();
    expect(screen.getByText('行业')).toBeInTheDocument();
    expect(screen.getByText('领涨')).toBeInTheDocument();
    expect(screen.getByText('+2.31%')).toBeInTheDocument();
    expect(screen.getByText('领跌')).toBeInTheDocument();
    expect(screen.getByText('-1.20%')).toBeInTheDocument();
    expect(screen.queryByText('中性')).not.toBeInTheDocument();
  });

  it('places related boards below action advice and renders more than three on one row', () => {
    const { container } = render(
      <ReportOverview
        meta={baseMeta}
        summary={baseSummary}
        details={{
          belongBoards: [
            { name: '白酒', type: '行业' },
            { name: '消费', type: '概念' },
            { name: '高端制造' },
            { name: '沪股通' },
          ],
        }}
      />,
    );

    const actionAdviceTitle = screen.getByText('操作建议');
    const relatedBoardsRegion = screen.getByRole('region', { name: '关联板块' });
    const boardList = container.querySelector('.home-related-board-list');

    expect(actionAdviceTitle.compareDocumentPosition(relatedBoardsRegion) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.getByText('沪股通')).toBeInTheDocument();
    expect(boardList).toHaveClass('flex-nowrap', 'overflow-x-auto');
  });

  it('shows board list when rankings are unavailable', () => {
    render(
      <ReportOverview
        meta={baseMeta}
        summary={baseSummary}
        details={{
          belongBoards: [{ name: '半导体', type: '行业' }],
        }}
      />,
    );

    expect(screen.getByText('关联板块')).toBeInTheDocument();
    expect(screen.getByText('半导体')).toBeInTheDocument();
    expect(screen.queryByText('中性')).not.toBeInTheDocument();
    expect(screen.queryByText('领涨')).not.toBeInTheDocument();
    expect(screen.queryByText('领跌')).not.toBeInTheDocument();
  });

  it('hides related boards section when no boards are available', () => {
    render(<ReportOverview meta={baseMeta} summary={baseSummary} details={{ belongBoards: [] }} />);

    expect(screen.queryByText('关联板块')).not.toBeInTheDocument();
  });

  it('fails open on malformed ranking payloads', () => {
    render(
      <ReportOverview
        meta={baseMeta}
        summary={baseSummary}
        details={{
          belongBoards: [{ name: ' 白酒 ' }],
          sectorRankings: {
            top: {} as unknown as never[],
            bottom: [{ name: '白酒', changePct: '-2.5%' as unknown as number }],
          },
        }}
      />,
    );

    expect(screen.getByText('关联板块')).toBeInTheDocument();
    expect(screen.getByText('白酒')).toBeInTheDocument();
    expect(screen.getByText('领跌')).toBeInTheDocument();
    expect(screen.getByText('-2.50%')).toBeInTheDocument();
  });
});

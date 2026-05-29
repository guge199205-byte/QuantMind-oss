import ExcelJS from 'exceljs';
import { saveAs } from 'file-saver';

export interface ExcelExportData {
  strategy_name: string;
  symbol: string;
  metrics: {
    [key: string]: any;
  };
  trades?: Array<{
    date: string;
    type: string;
    price: number;
    quantity: number;
    pnl?: number;
    [key: string]: any;
  }>;
  equity_curve?: {
    dates: string[];
    values: number[];
  };
  daily_returns?: {
    dates: string[];
    returns: number[];
  };
}

export interface TradeRecordExportRow {
  时间: string;
  方向: string;
  代码: string;
  名称: string;
  数量: number;
  价格: string;
  金额: number;
  状态: string;
}

export class ExcelExporter {
  private workbook: ExcelJS.Workbook;

  constructor() {
    this.workbook = new ExcelJS.Workbook();
    this.workbook.creator = 'QuantMind';
  }

  /**
   * 导出完整的回测数据
   */
  exportBacktest(data: ExcelExportData): void {
    // 1. 基本信息和指标工作表
    this.addMetricsSheet(data);

    // 2. 交易明细工作表
    if (data.trades && data.trades.length > 0) {
      this.addTradesSheet(data.trades);
    }

    // 3. 权益曲线工作表
    if (data.equity_curve) {
      this.addEquityCurveSheet(data.equity_curve);
    }

    // 4. 日收益率工作表
    if (data.daily_returns) {
      this.addDailyReturnsSheet(data.daily_returns);
    }
  }

  /**
   * 添加指标工作表
   */
  private addMetricsSheet(data: ExcelExportData): void {
    const metricsData = [
      ['回测报告'],
      [],
      ['基本信息'],
      ['策略名称', data.strategy_name],
      ['股票代码', data.symbol],
      [],
      ['性能指标', '值'],
      ['总收益率', this.formatPercent(data.metrics.total_return)],
      ['年化收益率', this.formatPercent(data.metrics.annual_return)],
      ['夏普比率', data.metrics.sharpe_ratio?.toFixed(2) || 'N/A'],
      ['最大回撤', this.formatPercent(data.metrics.max_drawdown)],
      ['波动率', this.formatPercent(data.metrics.volatility)],
      ['胜率', this.formatPercent(data.metrics.win_rate)],
      ['交易次数', data.metrics.total_trades || 0],
      ['盈利交易', data.metrics.winning_trades || 0],
      ['亏损交易', data.metrics.losing_trades || 0],
      ['平均盈利', this.formatPercent(data.metrics.avg_win)],
      ['平均亏损', this.formatPercent(data.metrics.avg_loss)],
      ['盈亏比', data.metrics.profit_loss_ratio?.toFixed(2) || 'N/A'],
    ];

    const worksheet = this.workbook.addWorksheet('指标摘要');
    metricsData.forEach(row => worksheet.addRow(row));
    worksheet.columns = [
      { width: 20 },
      { width: 15 },
    ];
  }

  /**
   * 添加交易明细工作表
   */
  private addTradesSheet(trades: ExcelExportData['trades']): void {
    if (!trades) return;

    const headers = ['日期', '类型', '价格', '数量', '盈亏', '佣金', '累计盈亏'];
    const rows = trades.map(trade => [
      trade.date,
      trade.type === 'buy' ? '买入' : '卖出',
      trade.price.toFixed(2),
      trade.quantity,
      trade.pnl?.toFixed(2) || '',
      trade.commission?.toFixed(2) || '',
      trade.cumulative_pnl?.toFixed(2) || '',
    ]);

    const worksheet = this.workbook.addWorksheet('交易明细');
    worksheet.addRow(headers);
    rows.forEach(r => worksheet.addRow(r));
    worksheet.columns = [
      { width: 12 },
      { width: 8 },
      { width: 10 },
      { width: 8 },
      { width: 12 },
      { width: 10 },
      { width: 12 },
    ];
  }

  /**
   * 添加权益曲线工作表
   */
  private addEquityCurveSheet(equity: ExcelExportData['equity_curve']): void {
    if (!equity) return;

    const headers = ['日期', '权益', '收益率'];
    const rows = equity.dates.map((date, index) => {
      const value = equity.values[index];
      const prevValue = index > 0 ? equity.values[index - 1] : equity.values[0];
      const returnRate = ((value - prevValue) / prevValue * 100).toFixed(2);

      return [
        date,
        value.toFixed(2),
        index > 0 ? returnRate + '%' : '0.00%',
      ];
    });

    const worksheet = this.workbook.addWorksheet('权益曲线');
    worksheet.addRow(headers);
    rows.forEach(r => worksheet.addRow(r));
    worksheet.columns = [
      { width: 12 },
      { width: 15 },
      { width: 12 },
    ];
  }

  /**
   * 添加日收益率工作表
   */
  private addDailyReturnsSheet(daily: ExcelExportData['daily_returns']): void {
    if (!daily) return;

    const headers = ['日期', '日收益率'];
    const rows = daily.dates.map((date, index) => [
      date,
      this.formatPercent(daily.returns[index]),
    ]);

    const worksheet = this.workbook.addWorksheet('日收益率');
    worksheet.addRow(headers);
    rows.forEach(r => worksheet.addRow(r));
    worksheet.columns = [
      { width: 12 },
      { width: 12 },
    ];
  }

  /**
   * 格式化百分比
   */
  private formatPercent(value: number | undefined): string {
    if (value === undefined || value === null) return 'N/A';
    return `${(value * 100).toFixed(2)}%`;
  }

  /**
   * 下载 Excel 文件
   */
  async download(filename: string = 'backtest-export.xlsx'): Promise<void> {
    const blob = await this.toBlob();
    saveAs(blob, filename);
  }

  /**
   * 导出为 Blob
   */
  async toBlob(): Promise<Blob> {
    const buffer = await this.workbook.xlsx.writeBuffer();
    return new Blob([buffer], {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    });
  }
}

export const exportTradeRecordsToExcel = async (
  rows: TradeRecordExportRow[],
  filename: string = 'trade-records.xlsx'
): Promise<void> => {
  const workbook = new ExcelJS.Workbook();
  workbook.creator = 'QuantMind';
  const worksheet = workbook.addWorksheet('交易记录');

  const headers: (keyof TradeRecordExportRow)[] = ['时间', '方向', '代码', '名称', '数量', '价格', '金额', '状态'];
  worksheet.addRow(headers);
  rows.forEach((row) => {
    worksheet.addRow(headers.map((header) => row[header]));
  });

  worksheet.columns = [
    { width: 22 },
    { width: 10 },
    { width: 14 },
    { width: 18 },
    { width: 10 },
    { width: 12 },
    { width: 14 },
    { width: 12 },
  ];

  const buffer = await workbook.xlsx.writeBuffer();
  const blob = new Blob([buffer], {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  });
  saveAs(blob, filename);
};

/**
 * 便捷导出函数
 */
export const exportBacktestToExcel = async (
  data: ExcelExportData,
  filename?: string
): Promise<void> => {
  const exporter = new ExcelExporter();
  exporter.exportBacktest(data);
  await exporter.download(filename);
};

/**
 * 导出批量回测结果对比
 */
export const exportBatchBacktestComparison = async (
  results: Array<{
    symbol: string;
    metrics: any;
  }>,
  filename: string = 'batch-backtest-comparison.xlsx'
): Promise<void> => {
  const workbook = new ExcelJS.Workbook();
  workbook.creator = 'QuantMind';
  const worksheet = workbook.addWorksheet('批量回测对比');

  // 创建对比表格
  const headers = [
    '股票代码',
    '总收益率',
    '年化收益率',
    '夏普比率',
    '最大回撤',
    '胜率',
    '交易次数',
  ];

  const rows = results.map(result => [
    result.symbol,
    `${(result.metrics.total_return * 100).toFixed(2)}%`,
    `${(result.metrics.annual_return * 100).toFixed(2)}%`,
    result.metrics.sharpe_ratio.toFixed(2),
    `${(result.metrics.max_drawdown * 100).toFixed(2)}%`,
    `${(result.metrics.win_rate * 100).toFixed(1)}%`,
    result.metrics.total_trades || 0,
  ]);

  worksheet.addRow(headers);
  rows.forEach(r => worksheet.addRow(r));
  worksheet.columns = [
    { width: 15 },
    { width: 12 },
    { width: 12 },
    { width: 12 },
    { width: 12 },
    { width: 10 },
    { width: 10 },
  ];

  const buffer = await workbook.xlsx.writeBuffer();
  const blob = new Blob([buffer], {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  });
  saveAs(blob, filename);
};

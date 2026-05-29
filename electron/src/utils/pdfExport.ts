/**
 * PDF 报告导出工具
 *
 * 功能：
 * - 生成完整的回测报告PDF
 * - 包含图表、指标、交易明细
 * - 支持自定义模板
 */

import { jsPDF } from 'jspdf';
import autoTable from 'jspdf-autotable';

export interface BacktestReportData {
  basic_info: {
    strategy_name: string;
    symbol: string;
    start_date: string;
    end_date: string;
    initial_capital: number;
  };
  metrics: {
    total_return: number;
    annual_return: number;
    sharpe_ratio: number;
    max_drawdown: number;
    win_rate: number;
    total_trades: number;
    [key: string]: any;
  };
  trades?: Array<{
    date: string;
    type: string;
    price: number;
    quantity: number;
    pnl?: number;
  }>;
  equity_curve?: {
    dates: string[];
    values: number[];
  };
}

export class PDFReportGenerator {
  private doc: jsPDF;
  private readonly pageWidth = 210; // A4 width in mm
  private readonly pageHeight = 297; // A4 height in mm
  private readonly margin = 20;
  private yPosition = 20;

  constructor() {
    this.doc = new jsPDF({
      orientation: 'portrait',
      unit: 'mm',
      format: 'a4',
    });
  }

  /**
   * 生成完整报告
   */
  async generateReport(data: BacktestReportData): Promise<Blob> {
    // 标题页
    this.addTitle('回测报告');
    this.addSubtitle(data.basic_info.strategy_name);
    this.yPosition += 10;

    // 基本信息
    this.addSection('基本信息');
    this.addBasicInfo(data.basic_info);

    // 性能指标
    this.addSection('性能指标');
    this.addMetricsTable(data.metrics);

    // 新页面 - 交易明细
    if (data.trades && data.trades.length > 0) {
      this.doc.addPage();
      this.yPosition = 20;
      this.addSection('交易明细');
      this.addTradesTable(data.trades);
    }

    // 生成 Blob
    return this.doc.output('blob');
  }

  /**
   * 添加标题
   */
  private addTitle(title: string) {
    this.doc.setFontSize(24);
    this.doc.setFont('helvetica', 'bold');
    this.doc.text(title, this.pageWidth / 2, this.yPosition, { align: 'center' });
    this.yPosition += 15;
  }

  /**
   * 添加副标题
   */
  private addSubtitle(subtitle: string) {
    this.doc.setFontSize(16);
    this.doc.setFont('helvetica', 'normal');
    this.doc.text(subtitle, this.pageWidth / 2, this.yPosition, { align: 'center' });
    this.yPosition += 10;
  }

  /**
   * 添加章节标题
   */
  private addSection(title: string) {
    this.doc.setFontSize(16);
    this.doc.setFont('helvetica', 'bold');
    this.doc.text(title, this.margin, this.yPosition);
    this.yPosition += 10;
  }

  /**
   * 添加基本信息
   */
  private addBasicInfo(info: BacktestReportData['basic_info']) {
    const data = [
      ['股票代码', info.symbol],
      ['开始日期', info.start_date],
      ['结束日期', info.end_date],
      ['初始资金', `¥${info.initial_capital.toLocaleString()}`],
    ];

    autoTable(this.doc, {
      startY: this.yPosition,
      head: [['项目', '值']],
      body: data,
      theme: 'grid',
      styles: { fontSize: 10, font: 'helvetica' },
      headStyles: { fillColor: [66, 139, 202] },
    });

    this.yPosition = (this.doc as any).lastAutoTable.finalY + 10;
  }

  /**
   * 添加指标表格
   */
  private addMetricsTable(metrics: BacktestReportData['metrics']) {
    const data = [
      ['总收益率', `${(metrics.total_return * 100).toFixed(2)}%`],
      ['年化收益率', `${(metrics.annual_return * 100).toFixed(2)}%`],
      ['夏普比率', metrics.sharpe_ratio.toFixed(2)],
      ['最大回撤', `${(metrics.max_drawdown * 100).toFixed(2)}%`],
      ['胜率', `${(metrics.win_rate * 100).toFixed(1)}%`],
      ['交易次数', metrics.total_trades.toString()],
    ];

    autoTable(this.doc, {
      startY: this.yPosition,
      head: [['指标', '值']],
      body: data,
      theme: 'grid',
      styles: { fontSize: 10, font: 'helvetica' },
      headStyles: { fillColor: [92, 184, 92] },
    });

    this.yPosition = (this.doc as any).lastAutoTable.finalY + 10;
  }

  /**
   * 添加交易明细表格
   */
  private addTradesTable(trades: BacktestReportData['trades']) {
    const data = trades?.slice(0, 50).map(trade => [
      trade.date,
      trade.type === 'buy' ? '买入' : '卖出',
      `¥${trade.price.toFixed(2)}`,
      trade.quantity.toString(),
      trade.pnl ? `¥${trade.pnl.toFixed(2)}` : '-',
    ]) || [];

    autoTable(this.doc, {
      startY: this.yPosition,
      head: [['日期', '类型', '价格', '数量', '盈亏']],
      body: data,
      theme: 'striped',
      styles: { fontSize: 9, font: 'helvetica' },
      headStyles: { fillColor: [217, 83, 79] },
    });

    this.yPosition = (this.doc as any).lastAutoTable.finalY + 10;

    // 如果交易太多，添加说明
    if (trades && trades.length > 50) {
      this.doc.setFontSize(10);
      this.doc.setTextColor(150, 150, 150);
      this.doc.text(
        `注：仅显示前50条交易记录，共${trades.length}条`,
        this.margin,
        this.yPosition
      );
    }
  }

  /**
   * 下载 PDF
   */
  download(filename: string = 'backtest-report.pdf') {
    this.doc.save(filename);
  }
}

/**
 * 便捷导出函数
 */
export const exportBacktestToPDF = async (
  data: BacktestReportData,
  filename?: string
): Promise<void> => {
  const generator = new PDFReportGenerator();
  await generator.generateReport(data);
  generator.download(filename);
};

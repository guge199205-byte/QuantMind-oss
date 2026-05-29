/**
 * 图表导出服务
 * 支持将图表导出为PNG/SVG格式
 */

export interface ChartExportOptions {
  filename?: string;
  format?: 'png' | 'svg';
  quality?: number; // 0-1, 仅用于PNG
  width?: number;
  height?: number;
  backgroundColor?: string;
}

export class ChartExporter {
  private defaultOptions: ChartExportOptions = {
    filename: 'chart.png',
    format: 'png',
    quality: 0.95,
    backgroundColor: '#ffffff'
  };

  /**
   * 导出Canvas为图片
   */
  exportCanvas(
    canvas: HTMLCanvasElement,
    options: ChartExportOptions = {}
  ): void {
    const opts = { ...this.defaultOptions, ...options };

    if (opts.format === 'png') {
      this.exportCanvasToPNG(canvas, opts);
    } else {
      throw new Error('Canvas can only be exported as PNG');
    }
  }

  /**
   * 导出SVG元素
   */
  exportSVG(
    svg: SVGElement,
    options: ChartExportOptions = {}
  ): void {
    const opts = { ...this.defaultOptions, ...options };
    const svgData = this.serializeSVG(svg);
    this.downloadFile(svgData, opts.filename!, 'image/svg+xml');
  }

  /**
   * 导出DOM元素为图片
   */
  async exportElement(
    element: HTMLElement,
    options: ChartExportOptions = {}
  ): Promise<void> {
    const opts = { ...this.defaultOptions, ...options };

    try {
      // 创建canvas
      const canvas = await this.elementToCanvas(element, opts);

      // 导出canvas
      this.exportCanvasToPNG(canvas, opts);
    } catch (error) {
      console.error('Failed to export element:', error);
      throw error;
    }
  }

  /**
   * 导出图表组件
   */
  async exportChartComponent(
    chartRef: React.RefObject<HTMLDivElement>,
    options: ChartExportOptions = {}
  ): Promise<void> {
    if (!chartRef.current) {
      throw new Error('Chart ref is not available');
    }

    await this.exportElement(chartRef.current, options);
  }

  /**
   * 批量导出多个图表
   */
  async exportMultipleCharts(
    charts: Array<{ element: HTMLElement; filename: string }>,
    options: Omit<ChartExportOptions, 'filename'> = {}
  ): Promise<void> {
    for (const chart of charts) {
      await this.exportElement(chart.element, {
        ...options,
        filename: chart.filename
      });
      // 添加延迟避免浏览器阻止下载
      await new Promise(resolve => setTimeout(resolve, 100));
    }
  }

  /**
   * 将Canvas导出为PNG
   */
  private exportCanvasToPNG(
    canvas: HTMLCanvasElement,
    options: ChartExportOptions
  ): void {
    const { filename, quality } = options;

    canvas.toBlob(
      blob => {
        if (!blob) {
          throw new Error('Failed to create blob from canvas');
        }

        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = filename!;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);

        setTimeout(() => URL.revokeObjectURL(url), 100);
      },
      'image/png',
      quality
    );
  }

  /**
   * 将元素转换为Canvas
   */
  private async elementToCanvas(
    element: HTMLElement,
    options: ChartExportOptions
  ): Promise<HTMLCanvasElement> {
    const { width, height, backgroundColor } = options;

    // 获取元素尺寸
    const rect = element.getBoundingClientRect();
    const w = width || rect.width;
    const h = height || rect.height;

    // 创建canvas
    const canvas = document.createElement('canvas');
    canvas.width = w * window.devicePixelRatio;
    canvas.height = h * window.devicePixelRatio;
    canvas.style.width = `${w}px`;
    canvas.style.height = `${h}px`;

    const ctx = canvas.getContext('2d')!;
    ctx.scale(window.devicePixelRatio, window.devicePixelRatio);

    // 设置背景色
    if (backgroundColor) {
      ctx.fillStyle = backgroundColor;
      ctx.fillRect(0, 0, w, h);
    }

    // 使用html2canvas的简化版本
    await this.renderElementToCanvas(element, ctx, w, h);

    return canvas;
  }

  /**
   * 渲染元素到Canvas
   */
  private async renderElementToCanvas(
    element: HTMLElement,
    ctx: CanvasRenderingContext2D,
    width: number,
    height: number
  ): Promise<void> {
    // 简化的渲染逻辑
    // 实际应用中应使用html2canvas库

    // 查找canvas子元素
    const canvases = element.querySelectorAll('canvas');
    if (canvases.length > 0) {
      // 如果有canvas子元素，直接绘制第一个
      ctx.drawImage(canvases[0], 0, 0, width, height);
    } else {
      // 使用SVG foreignObject进行渲染
      const data = `
        <svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}">
          <foreignObject width="100%" height="100%">
            <div xmlns="http://www.w3.org/1999/xhtml">
              ${element.outerHTML}
            </div>
          </foreignObject>
        </svg>
      `;

      const img = new Image();
      const svgBlob = new Blob([data], { type: 'image/svg+xml;charset=utf-8' });
      const url = URL.createObjectURL(svgBlob);

      return new Promise((resolve, reject) => {
        img.onload = () => {
          ctx.drawImage(img, 0, 0, width, height);
          URL.revokeObjectURL(url);
          resolve();
        };
        img.onerror = reject;
        img.src = url;
      });
    }
  }

  /**
   * 序列化SVG
   */
  private serializeSVG(svg: SVGElement): string {
    const serializer = new XMLSerializer();
    let svgString = serializer.serializeToString(svg);

    // 添加XML声明和xmlns
    if (!svgString.includes('xmlns="http://www.w3.org/2000/svg"')) {
      svgString = svgString.replace(
        '<svg',
        '<svg xmlns="http://www.w3.org/2000/svg"'
      );
    }

    return svgString;
  }

  /**
   * 下载文件
   */
  private downloadFile(
    data: string,
    filename: string,
    mimeType: string
  ): void {
    const blob = new Blob([data], { type: mimeType });
    const url = URL.createObjectURL(blob);

    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    setTimeout(() => URL.revokeObjectURL(url), 100);
  }

  /**
   * 获取图表数据URL
   */
  getChartDataURL(
    element: HTMLElement,
    format: 'png' | 'jpeg' = 'png',
    quality: number = 0.95
  ): Promise<string> {
    return new Promise(async (resolve, reject) => {
      try {
        const canvas = await this.elementToCanvas(element, {
          format: 'png',
          quality
        });
        const dataURL = canvas.toDataURL(`image/${format}`, quality);
        resolve(dataURL);
      } catch (error) {
        reject(error);
      }
    });
  }
}

// 单例
export const chartExporter = new ChartExporter();

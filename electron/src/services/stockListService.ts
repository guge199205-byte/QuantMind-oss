/**
 * 股票列表服务
 * 从本地JSON文件加载股票列表，支持内存搜索
 */

interface Stock {
  symbol: string;
  code: string;
  market: string;
  name?: string;
}

interface StocksData {
  version: string;
  updated_at: string;
  total: number;
  stocks: Stock[];
}

class StockListService {
  private stocks: Stock[] = [];
  private loaded: boolean = false;
  private loading: boolean = false;
  private loadPromise: Promise<void> | null = null;

  /**
   * 加载股票列表
   */
  async load(): Promise<void> {
    if (this.loaded) return;
    if (this.loading) return this.loadPromise!;

    this.loading = true;
    this.loadPromise = this._loadData();

    try {
      await this.loadPromise;
    } finally {
      this.loading = false;
    }
  }

  private async _loadData(): Promise<void> {
    try {
      console.log('[StockList] 加载股票列表...');
      const response = await fetch('/data/stocks.min.json');

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data: StocksData = await response.json();
      this.stocks = data.stocks;
      this.loaded = true;

      console.log(`[StockList] 成功加载 ${data.total} 只股票 (版本: ${data.version})`);
    } catch (error) {
      console.error('[StockList] 加载失败:', error);
      throw error;
    }
  }

  /**
   * 搜索股票
   * @param query 搜索关键词（代码或名称）
   * @param limit 返回结果数量
   */
  search(query: string, limit: number = 10): Stock[] {
    if (!this.loaded || !query) {
      return [];
    }

    const upperQuery = query.toUpperCase();
    const results: Stock[] = [];

    for (const stock of this.stocks) {
      if (results.length >= limit) break;

      // 匹配代码
      if (stock.code.includes(upperQuery)) {
        results.push(stock);
        continue;
      }

      // 匹配完整symbol
      if (stock.symbol.toUpperCase().includes(upperQuery)) {
        results.push(stock);
        continue;
      }

      // 匹配名称（如果有）
      if (stock.name && stock.name.includes(query)) {
        results.push(stock);
      }
    }

    return results;
  }

  /**
   * 获取所有股票
   */
  getAll(): Stock[] {
    return this.stocks;
  }

  /**
   * 获取加载状态
   */
  isLoaded(): boolean {
    return this.loaded;
  }

  /**
   * 获取总数
   */
  getTotal(): number {
    return this.stocks.length;
  }
}

// 单例
export const stockListService = new StockListService();
export type { Stock };

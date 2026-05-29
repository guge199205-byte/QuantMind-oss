import axios, { AxiosInstance } from 'axios';
import { authService } from '../../auth/services/authService';
import type {
  Telegraph,
  GlobalStockIndex,
  KLineData,
  HotItem,
  HotEvent,
  StockBasic,
  LongTigerRankData,
  FollowedFund,
  StockChangesResponse,
} from '../types';

class GoStockService {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: this.getBaseUrl(),
      timeout: 60000,
      headers: { 'Content-Type': 'application/json' },
    });

    this.client.interceptors.request.use((config) => {
      const token = authService.getAccessToken();
      if (token && config.headers) {
        (config.headers as any).Authorization = `Bearer ${token}`;
      }
      return config;
    });
  }

  private getBaseUrl(): string {
    const host = window.location.hostname;
    const port = '8000';
    return `http://${host}:${port}/api/v1/admin/go-stock`;
  }

  // News
  async getTelegraph(timeout = 30): Promise<Telegraph[]> {
    const { data } = await this.client.get('/news/telegraph', {
      params: { timeout },
    });
    return data || [];
  }

  async getSinaNews(timeout = 30): Promise<Telegraph[]> {
    const { data } = await this.client.get('/news/sina', {
      params: { timeout },
    });
    return data || [];
  }

  async getTradingViewNews(): Promise<Telegraph[]> {
    const { data } = await this.client.get('/news/tradingview');
    return data || [];
  }

  async getNewsList(source = '', limit = 50): Promise<Telegraph[]> {
    const { data } = await this.client.get('/news/list', {
      params: { source, limit },
    });
    return data || [];
  }

  // Global Indexes
  async getGlobalIndexes(timeout = 30): Promise<any> {
    const { data } = await this.client.get('/indexes/global', {
      params: { timeout },
    });
    return data;
  }

  async getCachedIndexes(region = ''): Promise<GlobalStockIndex[]> {
    const { data } = await this.client.get('/indexes/cached', {
      params: { region },
    });
    return data || [];
  }

  // Industry
  async getIndustryRank(sort = 'changepercent', cnt = 20): Promise<any> {
    const { data } = await this.client.get('/industry/rank', {
      params: { sort, cnt },
    });
    return data;
  }

  async getIndustryMoney(fenlei = '', sort = 'changepercent'): Promise<any[]> {
    const { data } = await this.client.get('/industry/money', {
      params: { fenlei, sort },
    });
    return data || [];
  }

  // Rankings
  async getLongTiger(date?: string): Promise<LongTigerRankData[]> {
    const params: any = {};
    if (date) params.date = date;
    const { data } = await this.client.get('/rank/longtiger', { params });
    return data || [];
  }

  async getMoneyRank(sort = 'changepercent'): Promise<any[]> {
    const { data } = await this.client.get('/rank/money', {
      params: { sort },
    });
    return data || [];
  }

  // Hot
  async getHotStocks(size = 20, marketType = 'A'): Promise<HotItem[]> {
    const { data } = await this.client.get('/hot/stocks', {
      params: { size, marketType },
    });
    return data || [];
  }

  async getHotEvents(size = 20): Promise<HotEvent[]> {
    const { data } = await this.client.get('/hot/events', {
      params: { size },
    });
    return data || [];
  }

  async getHotTopics(size = 20): Promise<any[]> {
    const { data } = await this.client.get('/hot/topics', {
      params: { size },
    });
    return data || [];
  }

  // K-Line
  async getKLine(
    code: string,
    type = 'day',
    days = 120,
    adjust = ''
  ): Promise<KLineData[]> {
    const { data } = await this.client.get('/kline', {
      params: { code, type, days, adjust },
    });
    return data || [];
  }

  // Stock
  async getStockRealtime(codes: string): Promise<any[]> {
    const { data } = await this.client.get('/stock/realtime', {
      params: { codes },
    });
    return data || [];
  }

  async searchStock(key: string): Promise<StockBasic[]> {
    const { data } = await this.client.get('/stock/search', {
      params: { key },
    });
    return data || [];
  }

  // Research
  async getStockResearch(code: string, days = 30): Promise<any[]> {
    const { data } = await this.client.get('/research/stock', {
      params: { code, days },
    });
    return data || [];
  }

  async getIndustryResearch(code: string, days = 30): Promise<any[]> {
    const { data } = await this.client.get('/research/industry', {
      params: { code, days },
    });
    return data || [];
  }

  async getStockNotice(stocks: string): Promise<any[]> {
    const { data } = await this.client.get('/research/notice', {
      params: { stocks },
    });
    return data || [];
  }

  // EastMoney AI Tools
  async getEarningsReview(query: string, reportDate = ''): Promise<string> {
    const { data } = await this.client.get('/em/earnings', {
      params: { query, reportDate },
    });
    return data?.result || '';
  }

  async getFinancialQA(query: string, deepThink = false): Promise<string> {
    const { data } = await this.client.get('/em/qa', {
      params: { query, deepThink: String(deepThink) },
    });
    return data?.result || '';
  }

  async getEmIndustryResearch(query: string): Promise<string> {
    const { data } = await this.client.get('/em/industry', {
      params: { query },
    });
    return data?.result || '';
  }

  async getTrackingReport(query: string): Promise<string> {
    const { data } = await this.client.get('/em/tracking', {
      params: { query },
    });
    return data?.result || '';
  }

  async getFinanceSearch(query: string): Promise<string> {
    const { data } = await this.client.get('/em/search', {
      params: { query },
    });
    return data?.result || '';
  }

  async getComparableCompany(query: string): Promise<string> {
    const { data } = await this.client.get('/em/comparable', {
      params: { query },
    });
    return data?.result || '';
  }

  async getHotspot(query: string): Promise<string> {
    const { data } = await this.client.get('/em/hotspot', {
      params: { query },
    });
    return data?.result || '';
  }

  // Money Flow
  async getMoneyTrend(code: string, days = 10): Promise<any[]> {
    const { data } = await this.client.get('/money/trend', {
      params: { code, days },
    });
    return data || [];
  }

  // Stock Changes
  async getStockChanges(
    changeTypes: number[] = [],
    pageIndex = 1,
    pageSize = 50
  ): Promise<StockChangesResponse> {
    const params: any = { pageIndex, pageSize };
    if (changeTypes.length > 0) {
      params.changeTypes = changeTypes.join(',');
    }
    const { data } = await this.client.get('/changes', { params });
    return data || { total: 0, data: [] };
  }

  // Statistics
  async getTodayStatistics(): Promise<any[]> {
    const { data } = await this.client.get('/statistics/today');
    return data || [];
  }

  async getRecentStatistics(days = 7): Promise<any[]> {
    const { data } = await this.client.get('/statistics/recent', {
      params: { days },
    });
    return data || [];
  }

  // Fund
  async getFundList(key: string): Promise<any[]> {
    const { data } = await this.client.get('/fund/list', {
      params: { key },
    });
    return data || [];
  }

  async getFollowedFunds(): Promise<FollowedFund[]> {
    const { data } = await this.client.get('/fund/followed');
    return data || [];
  }

  // Calendar
  async getInvestCalendar(yearMonth: string): Promise<any[]> {
    const { data } = await this.client.get('/calendar/invest', {
      params: { yearMonth },
    });
    return data || [];
  }

  async getClsCalendar(): Promise<any[]> {
    const { data } = await this.client.get('/calendar/cls');
    return data || [];
  }
}

export const goStockService = new GoStockService();

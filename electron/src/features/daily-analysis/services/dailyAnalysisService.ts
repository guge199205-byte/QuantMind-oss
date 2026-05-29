import axios, { AxiosInstance } from 'axios';
import { authService } from '../../auth/services/authService';
import type {
  AnalyzeRequest,
  AnalysisResultResponse,
  TaskAccepted,
  TaskListResponse,
  TaskStatus,
  StockSearchResult,
  MarketReviewRequest,
  MarketReviewAccepted,
} from '../types';

class DailyAnalysisService {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: this.getBaseUrl(),
      timeout: 120000,
      headers: { 'Content-Type': 'application/json' },
    });

    // Auth interceptor
    this.client.interceptors.request.use((config) => {
      const token = authService.getAccessToken();
      if (token && config.headers) {
        (config.headers as any).Authorization = `Bearer ${token}`;
      }
      return config;
    });

    this.client.interceptors.response.use(
      (r) => r,
      async (e) => authService.handle401Error(e, this.client),
    );
  }

  private getBaseUrl(): string {
    // In production, proxy through the admin API
    return '/api/v1/admin/daily-analysis';
  }

  private unwrap<T>(resp: any): T {
    const d = resp?.data;
    if (d && d.success !== undefined && d.data !== undefined) return d.data as T;
    if (d && d.success !== undefined) return d as T;
    return d as T;
  }

  // Analysis endpoints
  async triggerAnalysis(request: AnalyzeRequest): Promise<TaskAccepted> {
    const resp = await this.client.post('/analysis/analyze', request);
    return this.unwrap<TaskAccepted>(resp);
  }

  async getTaskStatus(taskId: string): Promise<TaskStatus> {
    const resp = await this.client.get(`/analysis/status/${taskId}`);
    return this.unwrap<TaskStatus>(resp);
  }

  async getTaskList(status?: string, limit = 20): Promise<TaskListResponse> {
    const params: Record<string, any> = { limit };
    if (status) params.status = status;
    const resp = await this.client.get('/analysis/tasks', { params });
    return this.unwrap<TaskListResponse>(resp);
  }

  // Market review
  async triggerMarketReview(request?: MarketReviewRequest): Promise<MarketReviewAccepted> {
    const resp = await this.client.post('/analysis/market-review', request || {});
    return this.unwrap<MarketReviewAccepted>(resp);
  }

  // History endpoints
  async getHistory(params?: {
    code?: string;
    limit?: number;
    offset?: number;
    report_type?: string;
  }): Promise<any> {
    const resp = await this.client.get('/history/reports', { params });
    return this.unwrap(resp);
  }

  async getReportDetail(queryId: string): Promise<any> {
    const resp = await this.client.get(`/history/reports/${queryId}`);
    return this.unwrap(resp);
  }

  // Stock search
  async searchStocks(keyword: string, limit = 10): Promise<StockSearchResult[]> {
    const resp = await this.client.get('/stocks/search', {
      params: { keyword, limit },
    });
    return this.unwrap<StockSearchResult[]>(resp);
  }

  // SSE connection for real-time task updates
  createTaskStream(): EventSource {
    const token = authService.getAccessToken();
    const baseUrl = this.getBaseUrl();
    const url = `${baseUrl}/analysis/tasks/stream`;
    // EventSource doesn't support custom headers, so we pass token as query param
    return new EventSource(`${url}?token=${token}`);
  }
}

export const dailyAnalysisService = new DailyAnalysisService();

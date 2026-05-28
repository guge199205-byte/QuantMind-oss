import axios, { AxiosInstance } from 'axios';
import { authService } from '../../auth/services/authService';
import { SERVICE_ENDPOINTS } from '../../../config/services';

/** 健康矩阵单元格 */
export interface HealthCell {
    field: string;
    source: string;
    is_primary: boolean;
    registered: boolean;
    last_success_at?: string | null;
    last_error_at?: string | null;
    error_rate_1h: number;
    avg_latency_ms: number;
    fallback_triggered_count: number;
}

export interface HealthMatrix {
    market: string;
    fields: string[];
    sources: string[];
    cells: HealthCell[];
    timestamp: string;
}

export interface SourceSummary {
    name: string;
    class: string;
    markets: string[];
    field_count: number;
    covered_field_count: number;
    health_summary: {
        last_success_at?: string | null;
        last_error_at?: string | null;
        last_error_msg?: string | null;
        error_rate_1h?: number;
        avg_latency_ms?: number;
    };
}

export interface FieldCoverageRow {
    field: string;
    tier: string;
    primary: string;
    fallbacks: string[];
    /** 后端为 boolean（是否参与共识投票）；旧版可能给数组，做兼容。 */
    consensus: boolean | string[];
    cleanup?: string[];
}

export interface QualityAlert {
    id: number;
    alert_type: string;
    severity: string;
    market?: string | null;
    field?: string | null;
    source?: string | null;
    symbol?: string | null;
    trade_date?: string | null;
    message: string;
    details?: any;
    acknowledged: boolean;
    acknowledged_by?: string | null;
    acknowledged_at?: string | null;
    created_at: string;
}

export interface FreshnessItem {
    field: string;
    source: string;
    is_primary: boolean;
    last_success_at?: string | null;
    last_error_at?: string | null;
    days_stale: number | null;
    freshness: 'fresh' | 'stale' | 'outdated' | 'unknown';
    avg_latency_ms: number;
    error_rate_1h: number;
}

export interface OnlineStatusItem {
    name: string;
    class: string;
    markets: string[];
    fields: string[];
    status: 'online' | 'error' | 'unavailable' | 'unknown';
    latency_ms: number | null;
    error?: string | null;
    checked_at: string;
}

class DataPlatformService {
    private axiosInstance: AxiosInstance;
    private readonly baseURL =
        (import.meta as any).env?.VITE_USER_API_URL || SERVICE_ENDPOINTS.USER_SERVICE;

    constructor() {
        this.axiosInstance = axios.create({
            baseURL: this.baseURL,
            timeout: 30000,
            headers: { 'Content-Type': 'application/json' },
        });

        this.axiosInstance.interceptors.request.use((config) => {
            const token = authService.getAccessToken();
            if (token && config.headers) {
                (config.headers as any).Authorization = `Bearer ${token}`;
            }
            let tenantId = 'default';
            try {
                const raw = localStorage.getItem('user');
                if (raw) {
                    const u = JSON.parse(raw);
                    if (u?.tenant_id) tenantId = String(u.tenant_id).trim();
                }
            } catch (e) {}
            if (config.headers) {
                (config.headers as any)['X-Tenant-Id'] = tenantId;
            }
            return config;
        });

        this.axiosInstance.interceptors.response.use(
            (response) => response,
            async (error) => authService.handle401Error(error, this.axiosInstance),
        );
    }

    private unwrap<T>(resp: any): T {
        const d = resp?.data;
        if (d && d.success && d.data) return d.data as T;
        return d as T;
    }

    async listMarkets(): Promise<{ markets: string[]; timestamp: string }> {
        const resp = await this.axiosInstance.get('/admin/data-platform/markets');
        return this.unwrap(resp);
    }

    async listSources(): Promise<{ sources: SourceSummary[]; timestamp: string }> {
        const resp = await this.axiosInstance.get('/admin/data-platform/sources');
        return this.unwrap(resp);
    }

    async getSourceHealth(name: string): Promise<{ source: string; fields: Record<string, any>; timestamp: string }> {
        const resp = await this.axiosInstance.get(`/admin/data-platform/sources/${name}/health`);
        return this.unwrap(resp);
    }

    async getHealthMatrix(market: string): Promise<HealthMatrix> {
        const resp = await this.axiosInstance.get('/admin/data-platform/health-matrix', {
            params: { market },
        });
        return this.unwrap(resp);
    }

    async getFieldCoverage(): Promise<{ coverage: Record<string, FieldCoverageRow[]>; timestamp: string }> {
        const resp = await this.axiosInstance.get('/admin/data-platform/field-coverage');
        return this.unwrap(resp);
    }

    async listAlerts(params: {
        severity?: string;
        market?: string;
        field?: string;
        acknowledged?: boolean;
        limit?: number;
        offset?: number;
    }): Promise<{ total: number; items: QualityAlert[]; timestamp: string }> {
        const resp = await this.axiosInstance.get('/admin/data-platform/quality-alerts', {
            params,
        });
        return this.unwrap(resp);
    }

    async ackAlert(alertId: number, note?: string): Promise<{ alert_id: number; acknowledged_by: string }> {
        const resp = await this.axiosInstance.post(
            `/admin/data-platform/quality-alerts/${alertId}/ack`,
            { note },
        );
        return this.unwrap(resp);
    }

    async triggerSync(
        name: string,
        payload: { market: string; field: string; symbols: string[] },
    ): Promise<{ source: string; results: Array<any> }> {
        const resp = await this.axiosInstance.post(`/admin/data-platform/sources/${name}/sync`, payload);
        return this.unwrap(resp);
    }

    async sweepMarket(payload: {
        market: string;
        field: string;
        symbols: string[];
        include_fallbacks?: boolean;
    }): Promise<{
        market: string;
        field: string;
        sources: string[];
        symbols: string[];
        summary: { ok: number; failed: number };
        per_source: Array<{ source: string; results: Array<any> }>;
        aggregated: Array<any>;
        timestamp: string;
    }> {
        const resp = await this.axiosInstance.post('/admin/data-platform/sweep', payload);
        return this.unwrap(resp);
    }

    async getFreshness(market: string): Promise<{ market: string; items: FreshnessItem[]; timestamp: string }> {
        const resp = await this.axiosInstance.get('/admin/data-platform/freshness', {
            params: { market },
            timeout: 30000,
        });
        return this.unwrap(resp);
    }

    async getOnlineStatus(): Promise<{
        items: OnlineStatusItem[];
        total: number;
        online: number;
        offline: number;
        timestamp: string;
    }> {
        const resp = await this.axiosInstance.get('/admin/data-platform/online-status', {
            timeout: 120000, // 在线检测可能较慢
        });
        return this.unwrap(resp);
    }
}

export const dataPlatformService = new DataPlatformService();

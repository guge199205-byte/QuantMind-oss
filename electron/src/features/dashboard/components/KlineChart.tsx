import React, { useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import type { KlineItem } from '../services/dataDashboardService';

interface KlineChartProps {
    data: KlineItem[];
    symbol: string;
    height?: number;
}

function calcMA(values: number[], period: number): (number | null)[] {
    const result: (number | null)[] = [];
    for (let i = 0; i < values.length; i++) {
        if (i < period - 1) {
            result.push(null);
        } else {
            let sum = 0;
            for (let j = 0; j < period; j++) {
                sum += values[i - j];
            }
            result.push(+(sum / period).toFixed(2));
        }
    }
    return result;
}

export const KlineChart: React.FC<KlineChartProps> = ({ data, symbol, height = 500 }) => {
    const option = useMemo(() => {
        if (!data?.length) return {};

        const dates = data.map((d) => d.date);
        const ohlc = data.map((d) => [d.open, d.close, d.low, d.high]);
        const volumes = data.map((d) => d.volume);
        const closes = data.map((d) => d.close);

        const ma5 = calcMA(closes, 5);
        const ma10 = calcMA(closes, 10);
        const ma20 = calcMA(closes, 20);
        const ma60 = calcMA(closes, 60);

        return {
            animation: false,
            title: {
                text: `${symbol} K线图`,
                left: 'center',
                textStyle: { fontSize: 14, fontWeight: 'normal' },
            },
            tooltip: {
                trigger: 'axis',
                axisPointer: { type: 'cross' },
                backgroundColor: 'rgba(255,255,255,0.95)',
                borderColor: '#e5e7eb',
                borderWidth: 1,
                textStyle: { color: '#374151', fontSize: 12 },
                formatter: (params: any) => {
                    if (!params?.length) return '';
                    const idx = params[0].dataIndex;
                    const d = data[idx];
                    if (!d) return '';
                    const change = d.close - d.open;
                    const pct = d.open ? ((change / d.open) * 100).toFixed(2) : '0.00';
                    const color = change >= 0 ? '#ef4444' : '#10b981';
                    return `
                        <div style="font-size:12px;line-height:1.8">
                            <div style="font-weight:600;margin-bottom:2px">${d.date}</div>
                            <div>开盘: <span style="color:${color}">${d.open.toFixed(2)}</span></div>
                            <div>收盘: <span style="color:${color}">${d.close.toFixed(2)}</span></div>
                            <div>最高: <span style="color:${color}">${d.high.toFixed(2)}</span></div>
                            <div>最低: <span style="color:${color}">${d.low.toFixed(2)}</span></div>
                            <div>涨跌: <span style="color:${color}">${change >= 0 ? '+' : ''}${change.toFixed(2)} (${change >= 0 ? '+' : ''}${pct}%)</span></div>
                            <div>成交量: ${(d.volume / 10000).toFixed(0)}万</div>
                        </div>`;
                },
            },
            legend: {
                data: ['K线', 'MA5', 'MA10', 'MA20', 'MA60'],
                top: 30,
                textStyle: { fontSize: 11 },
            },
            grid: [
                { left: '8%', right: '3%', top: '12%', height: '55%' },
                { left: '8%', right: '3%', top: '73%', height: '18%' },
            ],
            xAxis: [
                {
                    type: 'category',
                    data: dates,
                    gridIndex: 0,
                    axisLabel: { fontSize: 10, color: '#9ca3af' },
                    axisLine: { lineStyle: { color: '#e5e7eb' } },
                },
                {
                    type: 'category',
                    data: dates,
                    gridIndex: 1,
                    axisLabel: { show: false },
                    axisLine: { lineStyle: { color: '#e5e7eb' } },
                },
            ],
            yAxis: [
                {
                    scale: true,
                    gridIndex: 0,
                    splitLine: { lineStyle: { type: 'dashed', color: '#f3f4f6' } },
                    axisLabel: { fontSize: 10, color: '#9ca3af' },
                },
                {
                    scale: true,
                    gridIndex: 1,
                    splitNumber: 2,
                    axisLabel: {
                        fontSize: 10,
                        color: '#9ca3af',
                        formatter: (v: number) => (v >= 1e8 ? (v / 1e8).toFixed(0) + '亿' : v >= 1e4 ? (v / 1e4).toFixed(0) + '万' : String(v)),
                    },
                    splitLine: { lineStyle: { type: 'dashed', color: '#f3f4f6' } },
                },
            ],
            dataZoom: [
                { type: 'inside', xAxisIndex: [0, 1], start: 60, end: 100 },
                { show: true, xAxisIndex: [0, 1], bottom: '2%', height: 18, start: 60, end: 100 },
            ],
            series: [
                {
                    name: 'K线',
                    type: 'candlestick',
                    xAxisIndex: 0,
                    yAxisIndex: 0,
                    data: ohlc,
                    itemStyle: {
                        color: '#ef4444',
                        color0: '#10b981',
                        borderColor: '#ef4444',
                        borderColor0: '#10b981',
                    },
                },
                {
                    name: 'MA5',
                    type: 'line',
                    xAxisIndex: 0,
                    yAxisIndex: 0,
                    data: ma5,
                    smooth: true,
                    lineStyle: { width: 1 },
                    symbol: 'none',
                },
                {
                    name: 'MA10',
                    type: 'line',
                    xAxisIndex: 0,
                    yAxisIndex: 0,
                    data: ma10,
                    smooth: true,
                    lineStyle: { width: 1 },
                    symbol: 'none',
                },
                {
                    name: 'MA20',
                    type: 'line',
                    xAxisIndex: 0,
                    yAxisIndex: 0,
                    data: ma20,
                    smooth: true,
                    lineStyle: { width: 1 },
                    symbol: 'none',
                },
                {
                    name: 'MA60',
                    type: 'line',
                    xAxisIndex: 0,
                    yAxisIndex: 0,
                    data: ma60,
                    smooth: true,
                    lineStyle: { width: 1 },
                    symbol: 'none',
                },
                {
                    name: '成交量',
                    type: 'bar',
                    xAxisIndex: 1,
                    yAxisIndex: 1,
                    data: volumes,
                    itemStyle: {
                        color: (params: any) => {
                            const idx = params.dataIndex;
                            if (idx > 0 && data[idx]) {
                                return data[idx].close >= data[idx].close ? '#ef4444' : '#10b981';
                            }
                            return '#3b82f6';
                        },
                    },
                },
            ],
        };
    }, [data, symbol]);

    if (!data?.length) {
        return (
            <div style={{ height, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#9ca3af' }}>
                暂无K线数据
            </div>
        );
    }

    return (
        <ReactECharts
            option={option}
            style={{ height, width: '100%' }}
            notMerge
            lazyUpdate
        />
    );
};

import pandas as pd
import numpy as np
import asyncio
from sqlalchemy import text
from backend.shared.database_manager_v2 import get_session

OHLCV_PATH = "/Users/qusong/git/quantmind/data/ohlcv_complete_2016_2026.parquet"
FEATURES_PATH = "/Users/qusong/git/quantmind/data/feature_snapshots/model_features_2026.parquet"

async def update_data_pipeline():
    print(f"Reading OHLCV from {OHLCV_PATH}...")
    df = pd.read_parquet(OHLCV_PATH)
    df['trade_date'] = pd.to_datetime(df['trade_date']).dt.date
    
    # 基础还原 (未复权比例)
    df['close_unadj'] = df['close'] / df['factor']
    df['high_unadj'] = df['high'] / df['factor']
    df['low_unadj'] = df['low'] / df['factor']
    df['open_unadj'] = df['open'] / df['factor']
    df['amount_yuan'] = df['volume'] * df['close_unadj']
    df['adj_factor'] = df['factor'].astype(float)
    
    df = df.sort_values(['symbol', 'trade_date'])
    
    print("Computing comprehensive technical indicators (Unadjusted scale)...")
    # MACD & KDJ
    def get_macd(series):
        e1, e2 = series.ewm(span=12, adjust=False).mean(), series.ewm(span=26, adjust=False).mean()
        dif = e1 - e2
        dea = dif.ewm(span=9, adjust=False).mean()
        return pd.DataFrame({'dif': dif, 'dea': dea, 'hist': dif - dea})
    df[['macd_dif', 'macd_dea', 'macd_hist']] = df.groupby('symbol')['close_unadj'].apply(get_macd).reset_index(level=0, drop=True)
    
    def get_kdj(group):
        low_min, high_max = group['low_unadj'].rolling(9).min(), group['high_unadj'].rolling(9).max()
        rsv = (group['close_unadj'] - low_min) / (high_max - low_min + 1e-9) * 100
        k = rsv.ewm(com=2, adjust=False).mean()
        d = k.ewm(com=2, adjust=False).mean()
        return pd.DataFrame({'k': k, 'd': d, 'j': 3 * k - 2 * d})
    df[['kdj_k', 'kdj_d', 'kdj_j']] = df.groupby('symbol', group_keys=False).apply(get_kdj)

    # Moving Averages (MA) & Gaps
    for p in [5, 10, 20, 60]:
        df[f'ma{p}'] = df.groupby('symbol')['close_unadj'].transform(lambda x: x.rolling(p).mean())
        df[f'ma_gap_{p}'] = (df['close_unadj'] / df[f'ma{p}'] - 1) * 100

    # Volatility
    df['ret'] = df.groupby('symbol')['close_unadj'].pct_change()
    df['vol_std_20'] = df.groupby('symbol')['ret'].transform(lambda x: x.rolling(20).std() * 100)
    
    # Load Features
    print(f"Reading Features from {FEATURES_PATH}...")
    df_feat = pd.read_parquet(FEATURES_PATH)
    df_feat['trade_date'] = pd.to_datetime(df_feat['trade_date']).dt.date
    
    df = pd.merge(
        df, 
        df_feat[['symbol', 'trade_date', 'style_ln_mv_total', 'style_ln_mv_float', 'flow_large_net_amount', 'flow_net_amount', 'style_ep_ttm', 'style_bp', 'style_beta_20']], 
        on=['symbol', 'trade_date'], 
        how='inner'
    )
    
    df['total_mv_yuan'] = np.exp(df['style_ln_mv_total'].fillna(0))
    df['float_mv_yuan'] = np.exp(df['style_ln_mv_float'].fillna(0))
    df['turnover_calc'] = (df['amount_yuan'] / df['float_mv_yuan'] * 100).replace([np.inf, -np.inf], 0).fillna(0)
    df['main_flow_mln'] = df['flow_large_net_amount'].fillna(0) / 1000000.0
    df['net_flow_mln'] = df['flow_net_amount'].fillna(0) / 1000000.0
    df['pe_ttm_calc'] = df['style_ep_ttm'].apply(lambda x: 1.0/x if x > 0 else 0)

    # 筛选 2026 年
    df_2026 = df[df['trade_date'] >= pd.to_datetime('2026-01-01').date()]

    async with get_session() as session:
        dates = sorted(df_2026['trade_date'].unique())
        for dt in dates:
            batch = df_2026[df_2026['trade_date'] == dt]
            print(f"Updating {dt} ({len(batch)} stocks) with unadjusted K-line metrics...")
            
            sql = """
            UPDATE stock_daily_latest 
            SET amount = v.amount, turnover_rate = v.turnover,
                adj_factor = v.adj_factor,
                total_mv = v.total_mv, float_mv = v.float_mv, main_flow = v.main_flow, flow_net_amount = v.net_flow,
                ma5 = v.ma5, ma10 = v.ma10, ma20 = v.ma20, ma60 = v.ma60,
                ma_gap_5 = v.g5, ma_gap_10 = v.g10, ma_gap_20 = v.g20,
                macd_hist = v.m_hist, macd_dif = v.m_dif, macd_dea = v.m_dea,
                pe_ttm = v.pe, kdj_j = v.k_j, vol_std_20 = v.v20
            FROM unnest(
                CAST(:symbols AS text[]), CAST(:amounts AS double precision[]), CAST(:turnovers AS double precision[]),
                CAST(:adj_factors AS double precision[]),
                CAST(:total_mvs AS double precision[]), CAST(:float_mvs AS double precision[]),
                CAST(:main_flows AS double precision[]), CAST(:net_flows AS double precision[]),
                CAST(:ma5s AS double precision[]), CAST(:ma10s AS double precision[]), CAST(:ma20s AS double precision[]), CAST(:ma60s AS double precision[]),
                CAST(:g5s AS double precision[]), CAST(:g10s AS double precision[]), CAST(:g20s AS double precision[]),
                CAST(:m_hists AS double precision[]), CAST(:m_difs AS double precision[]), CAST(:m_deas AS double precision[]),
                CAST(:pes AS double precision[]), CAST(:k_js AS double precision[]), CAST(:v20s AS double precision[])
            ) AS v(symbol, amount, turnover, adj_factor, total_mv, float_mv, main_flow, net_flow, ma5, ma10, ma20, ma60, g5, g10, g20, m_hist, m_dif, m_dea, pe, k_j, v20)
            WHERE stock_daily_latest.symbol = v.symbol AND stock_daily_latest.trade_date = :trade_date
            """
            params = {
                'trade_date': dt,
                'symbols': batch['symbol'].tolist(),
                'amounts': batch['amount_yuan'].tolist(),
                'turnovers': batch['turnover_calc'].tolist(),
                'adj_factors': batch['factor'].astype(float).tolist(),
                'total_mvs': batch['total_mv_yuan'].tolist(),
                'float_mvs': batch['float_mv_yuan'].tolist(),
                'main_flows': batch['main_flow_mln'].tolist(),
                'net_flows': batch['net_flow_mln'].tolist(),
                'ma5s': batch['ma5'].fillna(0).tolist(),
                'ma10s': batch['ma10'].fillna(0).tolist(),
                'ma20s': batch['ma20'].fillna(0).tolist(),
                'ma60s': batch['ma60'].fillna(0).tolist(),
                'g5s': batch['ma_gap_5'].fillna(0).tolist(),
                'g10s': batch['ma_gap_10'].fillna(0).tolist(),
                'g20s': batch['ma_gap_20'].fillna(0).tolist(),
                'm_hists': batch['macd_hist'].fillna(0).tolist(),
                'm_difs': batch['macd_dif'].fillna(0).tolist(),
                'm_deas': batch['macd_dea'].fillna(0).tolist(),
                'pes': batch['pe_ttm_calc'].tolist(),
                'k_js': batch['kdj_j'].fillna(0).tolist(),
                'v20s': batch['vol_std_20'].fillna(0).tolist()
            }
            await session.execute(text(sql), params)
            await session.commit()

    print("Pipeline complete: All technical indicators and K-line metadata synchronized!")

if __name__ == '__main__':
    asyncio.run(update_data_pipeline())

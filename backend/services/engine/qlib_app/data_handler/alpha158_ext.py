"""Alpha158 extension handler with additional qlib_data features."""

from __future__ import annotations

from qlib.contrib.data.handler import Alpha158
from qlib.contrib.data.loader import Alpha158DL


class Alpha158Ext(Alpha158):
    """
    Extend Alpha158 with extra market microstructure and valuation signals.
    """

    def get_feature_config(self):
        base_fields, base_names = Alpha158DL.get_feature_config(
            {
                "kbar": {},
                "price": {"windows": [0], "feature": ["OPEN", "HIGH", "LOW", "VWAP"]},
                "rolling": {},
            }
        )

        ext_fields = [
            "$pb",
            "$pe",
            "$turnover",
            "$money/(Mean($money, 20)+1e-12)",
            "$net_buy_amt_ratio",
            "$large_order_net_ratio",
            "$buy_volume/($volume+1e-12)",
            "$sell_volume/($volume+1e-12)",
            "$buy_amount/($money+1e-12)",
            "$sell_amount/($money+1e-12)",
            "$buy_order_count/(Mean($buy_order_count, 20)+1e-12)",
            "$sell_order_count/(Mean($sell_order_count, 20)+1e-12)",
            "$realized_volatility",
            "$realized_skewness",
            "$realized_kurtosis",
            "$realized_range_volatility",
            "$realized_jump_volatility",
            "$jump_impact",
            "$jump_vol_ratio",
            "$bipower_variation",
            "$vpin_n8",
            "$vpin_n50",
            "$hf_realized_volatility",
            "$hf_realized_skewness",
            "$hf_realized_kurtosis",
            "$hf_realized_range_volatility",
            "$hf_total_volume/(Mean($hf_total_volume, 20)+1e-12)",
        ]
        ext_names = [
            "EXT_PB",
            "EXT_PE",
            "EXT_TURNOVER",
            "EXT_MONEY_NORM20",
            "EXT_NET_BUY_AMT_RATIO",
            "EXT_LARGE_ORDER_NET_RATIO",
            "EXT_BUY_VOL_RATIO",
            "EXT_SELL_VOL_RATIO",
            "EXT_BUY_AMT_RATIO",
            "EXT_SELL_AMT_RATIO",
            "EXT_BUY_ORDER_CNT_NORM20",
            "EXT_SELL_ORDER_CNT_NORM20",
            "EXT_RV",
            "EXT_RSKEW",
            "EXT_RKURT",
            "EXT_RRV",
            "EXT_RJV",
            "EXT_JUMP_IMPACT",
            "EXT_JUMP_VOL_RATIO",
            "EXT_BIPOWER_VAR",
            "EXT_VPIN8",
            "EXT_VPIN50",
            "EXT_HF_RV",
            "EXT_HF_RSKEW",
            "EXT_HF_RKURT",
            "EXT_HF_RRV",
            "EXT_HF_VOL_NORM20",
        ]

        return base_fields + ext_fields, base_names + ext_names

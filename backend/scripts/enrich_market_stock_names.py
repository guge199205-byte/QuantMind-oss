#!/usr/bin/env python3
"""Enrich market-specific stock tables with names from Tencent API.

Usage:
    python enrich_market_stock_names.py --market hk
    python enrich_market_stock_names.py --market us
    python enrich_market_stock_names.py --all
"""

import argparse
import sys
import time
import urllib.request
from pathlib import Path

_project_root = Path(__file__).resolve().parents[2]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from sqlalchemy import text

try:
    from backend.shared.database_pool import get_db
except ImportError:
    from shared.database_pool import get_db


def fetch_tencent_names(symbols: list[str], market: str) -> dict[str, str]:
    """Fetch stock names from Tencent API in batches."""
    names = {}
    prefix = "hk" if market == "hk" else "us"

    # Process in batches of 50
    batch_size = 50
    for i in range(0, len(symbols), batch_size):
        batch = symbols[i:i + batch_size]
        # HK codes need 5-digit padding (0001 -> 00001)
        if market == "hk":
            codes = ",".join(f"{prefix}{s.zfill(5)}" for s in batch)
        else:
            codes = ",".join(f"{prefix}{s}" for s in batch)
        url = f"https://qt.gtimg.cn/q={codes}"

        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://finance.qq.com/"
            })
            resp = urllib.request.urlopen(req, timeout=15)
            data = resp.read().decode("gbk")

            for line in data.strip().split(";"):
                line = line.strip()
                if not line:
                    continue
                # Format: v_hk00001="100~长和~00001~..."
                # Format: v_usAAPL="200~苹果~AAPL.OQ~..."
                match_start = line.find('"')
                if match_start < 0:
                    continue
                content = line[match_start + 1:].strip('"')
                parts = content.split("~")
                if len(parts) >= 3:
                    name = parts[1].strip()
                    code = parts[2].strip()
                    if name and code:
                        # For US, code might be like "AAPL.OQ", extract just "AAPL"
                        if "." in code:
                            code = code.split(".")[0]
                        # For HK, strip leading zeros to match DB format (00001 -> 0001)
                        if market == "hk":
                            code = code.lstrip("0") or "0"
                        names[code] = name

            if i + batch_size < len(symbols):
                time.sleep(0.5)  # Rate limiting

        except Exception as e:
            print(f"  Warning: batch {i}-{i+batch_size} failed: {e}")

    return names


def enrich_table(table_name: str, market: str):
    """Enrich a market-specific table with stock names."""
    print(f"\n=== Enriching {table_name} ({market}) ===")

    with get_db() as session:
        # Get all symbols
        rows = session.execute(
            text(f"SELECT DISTINCT symbol FROM {table_name} ORDER BY symbol")
        ).fetchall()
        symbols = [r[0] for r in rows]
        print(f"  Found {len(symbols)} symbols")

        if not symbols:
            print("  No symbols found, skipping")
            return

        # Fetch names from Tencent API
        print(f"  Fetching names from Tencent API...")
        names = fetch_tencent_names(symbols, market)
        print(f"  Got {len(names)} names")

        # Update database
        updated = 0
        for symbol, name in names.items():
            session.execute(
                text(f"UPDATE {table_name} SET name = :name WHERE symbol = :symbol"),
                {"name": name, "symbol": symbol}
            )
            updated += 1

        session.commit()
        print(f"  Updated {updated} rows")

        # Verify
        sample = session.execute(
            text(f"SELECT symbol, name FROM {table_name} WHERE name != symbol LIMIT 5")
        ).fetchall()
        if sample:
            print(f"  Sample updated names:")
            for r in sample:
                print(f"    {r[0]} -> {r[1]}")


def main():
    parser = argparse.ArgumentParser(description="Enrich market stock tables with names")
    parser.add_argument("--market", choices=["hk", "us"], help="Specific market")
    parser.add_argument("--all", action="store_true", help="All markets")
    args = parser.parse_args()

    if not args.market and not args.all:
        args.all = True

    MARKET_TABLES = {
        "hk": "stock_daily_latest_hk",
        "us": "stock_daily_latest_us",
    }

    markets = list(MARKET_TABLES.keys()) if args.all else [args.market]

    for market in markets:
        table = MARKET_TABLES[market]
        try:
            enrich_table(table, market)
        except Exception as e:
            print(f"  Error: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()

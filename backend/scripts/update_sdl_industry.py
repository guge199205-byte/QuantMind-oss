import os
import sys
import json
from pathlib import Path
import asyncio
from sqlalchemy import text
from backend.shared.database_manager_v2 import get_session

INDUSTRY_DIR = "/Users/qusong/git/quantmind/db/concept_data/industry/csrc1"

async def update_industry():
    print(f"Scanning industry files in: {INDUSTRY_DIR}")
    
    industry_map = {} # industry_name -> [symbols]
    
    for filename in os.listdir(INDUSTRY_DIR):
        if filename.endswith(".json"):
            path = os.path.join(INDUSTRY_DIR, filename)
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                concept = data.get('concept', '')
                # 去掉 CSRC1 前缀
                industry_name = concept.replace("CSRC1", "")
                stocks = data.get('stocks', [])
                
                # 转换代码格式: 600001.SH -> SH600001
                formatted_stocks = []
                for s in stocks:
                    parts = s.split('.')
                    if len(parts) == 2:
                        formatted_stocks.append(f"{parts[1]}{parts[0]}")
                
                industry_map[industry_name] = formatted_stocks
                print(f"Found industry '{industry_name}' with {len(formatted_stocks)} stocks.")

    async with get_session() as session:
        print("Updating PostgreSQL industry field...")
        total_updated = 0
        for name, symbols in industry_map.items():
            if not symbols: continue
            
            # 批量更新该行业下的所有股票
            res = await session.execute(
                text("UPDATE stock_daily_latest SET industry = :name WHERE symbol = ANY(:symbols)"),
                {"name": name, "symbols": list(symbols)}
            )
            total_updated += res.rowcount
            print(f"Updated {res.rowcount} rows for industry: {name}")
            await session.commit()
            
    print(f"Industry update complete! Total rows affected: {total_updated}")

if __name__ == '__main__':
    asyncio.run(update_industry())

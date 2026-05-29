"""
Manual Snapshot Fix - 手动生成初始快照脚本
"""

import asyncio
import os
import sys

# 添加项目根目录到路径
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)
os.environ["PYTHONPATH"] = base_dir

from sqlalchemy import select
from backend.shared.database_manager_v2 import init_database, get_db_manager, close_database
from backend.services.trade.portfolio.models import Portfolio
from backend.services.trade.portfolio.services.portfolio_service import PortfolioService

async def main():
    print("Initializing database...")
    await init_database()
    
    try:
        db_manager = get_db_manager()
        async with db_manager.get_master_session() as db:
            print("Querying active portfolios...")
            stmt = select(Portfolio).where(Portfolio.is_deleted == False)
            result = await db.execute(stmt)
            portfolios = result.scalars().all()
            
            print(f"Found {len(portfolios)} portfolios. Creating snapshots...")
            
            for portfolio in portfolios:
                try:
                    # 计算指标
                    await PortfolioService.calculate_portfolio_metrics(db, portfolio)
                    # 创建快照
                    snapshot = await PortfolioService.create_snapshot(db, portfolio)
                    print(f"✅ Created snapshot for Portfolio {portfolio.id} ({portfolio.name})")
                except Exception as e:
                    print(f"❌ Failed to snapshot portfolio {portfolio.id}: {e}")
            
            await db.commit()
            print("Done!")
            
    finally:
        await close_database()

if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python3
"""
智能策略生成与落库完整流程执行脚本
执行步骤：
1. 生成股票列表文件（使用筛选条件）
2. 参数传递与处理
3. 策略生成（调用LLM）
4. 策略落库到云端个人中心
5. 流程验证
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from uuid import uuid4

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from backend.services.engine.ai_strategy.api.schemas.generation import GenerateRequest
from backend.services.engine.ai_strategy.api.schemas.stock_pool import (
    ParseRequest,
    QueryPoolRequest,
)
from backend.services.engine.ai_strategy.api.schemas.strategy_params import (
    BuyRule,
    RiskConfig,
    SellRule,
)
from backend.services.engine.ai_strategy.models.stock_pool_file import StockPoolFile
from backend.services.engine.ai_strategy.services.strategy_cloud_storage import (
    StrategyCloudStorage,
)
from backend.services.engine.ai_strategy.steps.step1_stock_selection import parse_conditions as step1_parse
from backend.services.engine.ai_strategy.steps.step2_pool_confirmation import query_pool as step2_query
from backend.services.engine.ai_strategy.steps.step5_generation import generate_strategy as step5_generate
from backend.shared.database_pool import get_db


class StrategyGenerationFlow:
    """智能策略生成与落库流程"""

    def __init__(self, user_id: str = "00000001"):
        self.user_id = user_id
        self.tenant_id = "default"
        self.session_id = str(uuid4())
        self.storage = StrategyCloudStorage()
        self.results = {}

    def step1_generate_stock_list(self, conditions: List[Dict[str, Any]]) -> str:
        """步骤1: 生成股票列表文件"""
        print("\n" + "=" * 60)
        print("步骤1: 生成股票列表文件")
        print("=" * 60)

        parse_request = ParseRequest(conditions=conditions)
        parse_result = step1_parse(parse_request)
        dsl = parse_result.dsl
        print(f"✅ DSL生成成功: {dsl}")

        query_request = QueryPoolRequest(
            dsl=dsl,
            user_id=self.user_id,
            tenant_id=self.tenant_id,
            session_id=self.session_id,
        )

        query_result = step2_query(query_request)
        stock_list = query_result.items
        print(f"✅ 股票列表生成成功: {len(stock_list)} 只股票")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        temp_dir = Path("/tmp/strategy_generation")
        temp_dir.mkdir(parents=True, exist_ok=True)

        stock_file = temp_dir / f"stock_list_{timestamp}.txt"
        stock_codes = [item.symbol for item in stock_list]
        stock_file.write_text("\n".join(stock_codes), encoding="utf-8")

        print(f"✅ 股票列表文件已保存: {stock_file}")
        print(f"   文件大小: {stock_file.stat().st_size} 字节")

        self.results["stock_list"] = stock_list
        self.results["stock_file"] = str(stock_file)
        self.results["dsl"] = dsl

        return str(stock_file)

    async def step2_generate_strategy(
        self,
        stock_file: str,
        description: str,
        strategy_name: str,
        risk_level: str = "medium",
        style: str = "simple",
    ) -> Dict[str, Any]:
        """步骤2-3: 参数传递与策略生成"""
        print("\n" + "=" * 60)
        print("步骤2-3: 参数传递与策略生成")
        print("=" * 60)

        with open(stock_file, "r", encoding="utf-8") as f:
            stock_codes = [line.strip() for line in f if line.strip()]

        print("📋 传入参数:")
        print(f"   - 股票列表文件: {stock_file}")
        print(f"   - 股票数量: {len(stock_codes)}")
        print(f"   - 策略描述: {description}")
        print(f"   - 策略名称: {strategy_name}")
        print(f"   - 风险级别: {risk_level}")
        print(f"   - 策略风格: {style}")

        conditions = [
            {
                "type": "numeric",
                "factor": "market_cap",
                "operator": ">",
                "threshold": 100000000000,
            },
            {
                "type": "numeric",
                "factor": "pe_ttm",
                "operator": "<",
                "threshold": 30,
            },
            {
                "type": "numeric",
                "factor": "is_st",
                "operator": "==",
                "threshold": 0,
            },
        ]

        buy_rules = [
            BuyRule(
                name="等权重买入",
                description="等权重分配仓位",
            )
        ]

        sell_rules = [
            SellRule(
                name="止损",
                description="亏损超过10%时卖出",
            )
        ]

        risk_config = RiskConfig(
            maxPosition=0.6,
            maxDrawdown=0.15,
            rebalanceFrequency="monthly",
        )

        generate_request = GenerateRequest(
            description=description,
            conditions=conditions,
            buyRules=buy_rules,
            sellRules=sell_rules,
            risk=risk_config,
            stock_pool=stock_codes,
            strategy_name=strategy_name,
            risk_level=risk_level,
            style=style,
            user_id=self.user_id,
            tenant_id=self.tenant_id,
        )

        print("\n🤖 调用LLM生成策略...")
        try:
            generate_result = await step5_generate(generate_request)

            print("✅ 策略生成成功")
            print(f"   - 策略ID: {generate_result.strategy_id}")
            print(f"   - 代码长度: {len(generate_result.code)} 字符")

            self.results["strategy_result"] = generate_result
            self.results["strategy_id"] = generate_result.strategy_id

            return generate_result
        except Exception as e:
            print(f"❌ 策略生成失败: {e}")
            import traceback

            traceback.print_exc()
            raise

    async def step4_save_to_cloud(
        self, strategy_result: Dict[str, Any], strategy_name: str, description: str
    ) -> Dict[str, Any]:
        """步骤4: 策略落库到云端个人中心"""
        print("\n" + "=" * 60)
        print("步骤4: 策略落库到云端个人中心")
        print("=" * 60)

        strategy_id = self.results["strategy_id"]

        print("📤 保存策略文件到COS...")
        save_result = self.storage.save_strategy_files_to_cos(
            strategy_result=strategy_result,
            raw_response={"description": description, "strategy_name": strategy_name},
            strategy_id=strategy_id,
            user_id=self.user_id,
            user_description=description,
        )

        if save_result.get("success"):
            print("✅ 策略文件已保存到COS")
            print(f"   - 策略ID: {save_result['strategy_id']}")
            print(f"   - 用户ID: {save_result['user_id']}")
            print(f"   - 文件数量: {save_result['total_files']}")
            print(f"   - 存储路径: {save_result['storage_url']}")

            print("\n💾 保存股票池文件信息到数据库...")
            try:
                with get_db() as session:
                    existing = (
                        session.query(StockPoolFile)
                        .filter_by(
                            user_id=self.user_id,
                            session_id=self.session_id,
                            is_active=True,
                        )
                        .first()
                    )

                    if existing:
                        existing.is_active = False

                    stock_pool_record = StockPoolFile(
                        tenant_id=self.tenant_id,
                        user_id=self.user_id,
                        pool_name=strategy_name,
                        session_id=self.session_id,
                        file_key=f"strategies/{self.user_id}/{save_result['timestamp']}",
                        file_url=save_result.get("storage_url", ""),
                        relative_path=f"strategies/{self.user_id}/{save_result['timestamp']}",
                        format="txt",
                        file_size=Path(self.results["stock_file"]).stat().st_size,
                        stock_count=len(self.results["stock_list"]),
                        is_active=True,
                    )

                    session.add(stock_pool_record)
                    session.commit()

                    print("✅ 股票池文件信息已保存到数据库")
                    print(f"   - 记录ID: {stock_pool_record.id}")
                    print(f"   - 股票数量: {stock_pool_record.stock_count}")

            except Exception as e:
                print(f"⚠️  保存股票池文件信息失败: {e}")

            self.results["cloud_save_result"] = save_result
            return save_result
        else:
            print(f"❌ 保存失败: {save_result.get('error')}")
            return save_result

    def step5_verify_flow(self) -> bool:
        """步骤5: 流程验证"""
        print("\n" + "=" * 60)
        print("步骤5: 流程验证")
        print("=" * 60)

        checks = []

        stock_file = self.results.get("stock_file")
        if stock_file and Path(stock_file).exists():
            print(f"✅ 检查1: 股票列表文件存在 - {stock_file}")
            checks.append(True)
        else:
            print("❌ 检查1: 股票列表文件不存在")
            checks.append(False)

        strategy_result = self.results.get("strategy_result")
        if strategy_result and strategy_result.get("code"):
            print("✅ 检查2: 策略代码已生成")
            checks.append(True)
        else:
            print("❌ 检查2: 策略代码未生成")
            checks.append(False)

        cloud_save = self.results.get("cloud_save_result")
        if cloud_save and cloud_save.get("success"):
            print("✅ 检查3: 策略已保存到云端")
            checks.append(True)
        else:
            print("❌ 检查3: 策略未保存到云端")
            checks.append(False)

        try:
            with get_db() as session:
                record = (
                    session.query(StockPoolFile)
                    .filter_by(user_id=self.user_id, session_id=self.session_id, is_active=True)
                    .first()
                )

                if record:
                    print("✅ 检查4: 数据库记录已创建")
                    print(f"   - 记录ID: {record.id}")
                    print(f"   - 股票数量: {record.stock_count}")
                    checks.append(True)
                else:
                    print("❌ 检查4: 数据库记录未创建")
                    checks.append(False)
        except Exception as e:
            print(f"❌ 检查4: 数据库查询失败: {e}")
            checks.append(False)

        print("\n" + "=" * 60)
        if all(checks):
            print("🎉 所有检查通过！流程执行成功")
            print("=" * 60)
            return True
        else:
            failed = len([c for c in checks if not c])
            print(f"⚠️  {failed}/{len(checks)} 个检查失败")
            print("=" * 60)
            return False

    async def run_complete_flow(
        self,
        conditions: List[Dict[str, Any]],
        description: str,
        strategy_name: str,
        risk_level: str = "medium",
        style: str = "simple",
    ) -> Dict[str, Any]:
        """运行完整流程"""
        start_time = datetime.now()

        print("\n" + "🚀" * 30)
        print("智能策略生成与落库流程")
        print(f"用户ID: {self.user_id}")
        print(f"会话ID: {self.session_id}")
        print(f"开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("🚀" * 30)

        try:
            stock_file = self.step1_generate_stock_list(conditions)

            strategy_result = await self.step2_generate_strategy(
                stock_file=stock_file,
                description=description,
                strategy_name=strategy_name,
                risk_level=risk_level,
                style=style,
            )

            await self.step4_save_to_cloud(
                strategy_result=strategy_result,
                strategy_name=strategy_name,
                description=description,
            )

            success = self.step5_verify_flow()

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            print(f"\n⏱️  总耗时: {duration:.2f} 秒")

            return {
                "success": success,
                "session_id": self.session_id,
                "strategy_id": self.results.get("strategy_id"),
                "stock_count": len(self.results.get("stock_list", [])),
                "duration": duration,
                "results": self.results,
            }

        except Exception as e:
            print(f"\n❌ 流程执行失败: {e}")
            import traceback

            traceback.print_exc()
            return {
                "success": False,
                "error": str(e),
                "session_id": self.session_id,
            }


async def main():
    """主函数"""

    flow = StrategyGenerationFlow(user_id="00000001")

    conditions = [
        {
            "type": "numeric",
            "factor": "market_cap",
            "operator": ">",
            "threshold": 100000000000,
        },
        {
            "type": "numeric",
            "factor": "pe_ttm",
            "operator": "<",
            "threshold": 30,
        },
        {
            "type": "numeric",
            "factor": "is_st",
            "operator": "==",
            "threshold": 0,
        },
    ]

    description = """
    基于价值投资理念的选股策略：
    1. 选择市值大于100亿、PE小于30的非ST股票
    2. 采用等权重配置，控制单一股票仓位不超过5%
    3. 每月进行一次再平衡
    4. 设置止损线为-10%
    """

    strategy_name = "价值投资策略_智能生成"

    result = await flow.run_complete_flow(
        conditions=conditions,
        description=description,
        strategy_name=strategy_name,
        risk_level="medium",
        style="simple",
    )

    print("\n" + "=" * 60)
    print("流程执行结果")
    print("=" * 60)
    print(json.dumps(result, ensure_ascii=False, indent=2))

    return 0 if result["success"] else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

"""
第一个AI因子生成任务
使用DeepSeek自动生成量化因子
"""

import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


def generate_factor_with_ai(hypothesis, save_dir="./generated_factors"):
    """使用AI生成因子代码"""

    print("=" * 70)
    print("AI 因子生成任务")
    print("=" * 70)

    from openai import OpenAI

    # 创建DeepSeek客户端
    api_key = os.getenv("DEEPSEEK_API_KEY")
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

    print("\n[配置信息]")
    print(f"  API Base: {base_url}")
    print(f"  API Key: {api_key[:15]}...")

    client = OpenAI(api_key=api_key, base_url=f"{base_url}/v1")

    print("\n[研究假设]")
    print(f"  {hypothesis}")

    # 构建提示词
    prompt = f"""你是一个专业的量化研究员。请根据以下假设生成Python量化因子代码。

研究假设：
{hypothesis}

要求：
1. 使用pandas和numpy实现
2. 输入参数为DataFrame，包含以下列：['open', 'high', 'low', 'close', 'volume']
3. 返回一个Series，表示因子值
4. 函数名为 calculate_factor
5. 添加详细的中文注释
6. 包含参数说明和使用示例
7. 考虑边界情况处理（NaN、Inf等）
8. 代码要可以直接运行

请只返回完整的Python代码，不要有其他解释文字。"""

    print("\n[步骤1] 向DeepSeek发送请求...")
    print("  模型: deepseek-chat")

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {
                    "role": "system",
                    "content": "你是一个专业的量化研究员，擅长编写高质量的Python量化因子代码。",
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=2000,
            temperature=0.7,
        )

        print("✓ 请求成功")

    except Exception as e:
        print(f"✗ 请求失败: {e}")
        return None

        # 提取生成的代码
    generated_code = response.choices[0].message.content

    # 清理代码（移除markdown标记）
    if "```python" in generated_code:
        generated_code = generated_code.split("```python")[1].split("```")[0]
    elif "```" in generated_code:
        generated_code = generated_code.split("```")[1].split("```")[0]

    generated_code = generated_code.strip()

    print("\n[步骤2] 代码生成完成")
    code_lines = len(generated_code.split("\n"))
    print(f"  代码行数: {code_lines} 行")
    print(f"  使用tokens: {response.usage.total_tokens}")
    print(f"  输入tokens: {response.usage.prompt_tokens}")
    print(f"  输出tokens: {response.usage.completion_tokens}")

    # 估算成本（DeepSeek pricing）
    cost = (
        response.usage.prompt_tokens * 0.001 + response.usage.completion_tokens * 0.002
    ) / 1000
    print(f"  估算成本: ¥{cost:.6f} (约{cost*100:.4f}分)")

    # 保存代码
    save_path = Path(save_dir)
    save_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"factor_{timestamp}.py"
    filepath = save_path / filename

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f'''"""
自动生成的量化因子
生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
研究假设: {hypothesis}
"""

''')
        f.write(generated_code)

    print("\n[步骤3] 代码已保存")
    print(f"  文件路径: {filepath.absolute()}")

    return generated_code, filepath


def display_generated_code(code):
    """显示生成的代码"""
    print("\n" + "=" * 70)
    print("生成的因子代码")
    print("=" * 70)
    print(code)
    print("=" * 70)


def test_generated_factor(filepath):
    """测试生成的因子"""
    print("\n" + "=" * 70)
    print("测试生成的因子")
    print("=" * 70)

    try:
        print("\n[步骤1] 创建测试数据...")
        import numpy as np
        import pandas as pd

        # 创建模拟数据
        np.random.seed(42)
        n_days = 100
        dates = pd.date_range("2024-01-01", periods=n_days)

        # 模拟价格数据
        close_prices = 100 + np.cumsum(np.random.randn(n_days) * 2)
        high_prices = close_prices + np.random.rand(n_days) * 3
        low_prices = close_prices - np.random.rand(n_days) * 3
        open_prices = close_prices + np.random.randn(n_days) * 1
        volumes = np.random.randint(1000000, 10000000, n_days)

        df = pd.DataFrame(
            {
                "open": open_prices,
                "high": high_prices,
                "low": low_prices,
                "close": close_prices,
                "volume": volumes,
            },
            index=dates,
        )

        print(f"✓ 测试数据创建完成 ({n_days}天)")
        print(f"  价格范围: {df['close'].min():.2f} - {df['close'].max():.2f}")

        print("\n[步骤2] 加载因子代码...")

        # 动态导入因子模块
        import importlib

        spec = importlib.util.spec_from_file_location(
            "generated_factor", filepath)
        factor_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(factor_module)

<<<<<<< HEAD
        spec = importlib.util.spec_from_file_location("generated_factor", filepath)
        factor_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(factor_module)

        print("✓ 因子代码加载成功")

=======
        print("✓ 因子代码加载成功")

>>>>>>> refactor/service-cleanup
        print("\n[步骤3] 计算因子值...")

        # 调用因子函数
        factor_values = factor_module.calculate_factor(df)

        print("✓ 因子计算完成")

        # 分析因子
        print("\n[步骤4] 因子分析")
        print(f"  因子类型: {type(factor_values)}")
        print(f"  因子长度: {len(factor_values)}")
        print(f"  有效值数量: {factor_values.notna().sum()}")
        print(f"  缺失值数量: {factor_values.isna().sum()}")

        if factor_values.notna().sum() > 0:
            valid_values = factor_values.dropna()
            print("\n  因子统计:")
            print(f"    均值: {valid_values.mean():.6f}")
            print(f"    标准差: {valid_values.std():.6f}")
            print(f"    最小值: {valid_values.min():.6f}")
            print(f"    最大值: {valid_values.max():.6f}")
            print(f"    中位数: {valid_values.median():.6f}")

            # 显示前5个和后5个值
            print("\n  前5个因子值:")
            for i, (date, value) in enumerate(factor_values.head().items()):
                status = "✓" if pd.notna(value) else "✗"
                print(
                    f"    {date.strftime('%Y-%m-%d')}: {value:.6f if pd.notna(value) else 'NaN':>10s} {status}"
                )

            print("\n  后5个因子值:")
            for i, (date, value) in enumerate(factor_values.tail().items()):
                status = "✓" if pd.notna(value) else "✗"
                print(
                    f"    {date.strftime('%Y-%m-%d')}: {value:.6f if pd.notna(value) else 'NaN':>10s} {status}"
                )

        print("\n✓ 因子测试完成！")
        return True

    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """主函数"""
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 20 + "第一个AI因子生成任务" + " " * 28 + "║")
    print("╚" + "=" * 68 + "╝")
    print()

    # 定义几个研究假设供选择
    hypotheses = [
        {
            "name": "动量反转因子",
            "description": "短期超跌后的反弹效应：当股票在过去5天下跌超过8%且成交量萎缩时，未来3-5天可能反弹",
        },
        {
            "name": "波动率突破因子",
            "description": "价格突破布林带上轨且成交量放大时，表明趋势强劲，未来5-10天可能继续上涨",
        },
        {
            "name": "量价背离因子",
            "description": "价格创新高但成交量没有放大，可能表明上涨乏力，存在回调风险",
        },
        {
            "name": "多周期共振因子",
            "description": "5日、10日、20日均线同时向上且排列顺序正确，表明多周期趋势一致",
        },
    ]

    print("请选择一个研究假设，或输入自定义假设：\n")
    for i, h in enumerate(hypotheses, 1):
        print(f"  {i}. {h['name']}")
        print(f"     {h['description']}\n")
    print("  5. 自定义假设")

    print()
    choice = input("请输入选择 (1-5): ").strip()

    if choice in ["1", "2", "3", "4"]:
        idx = int(choice) - 1
        hypothesis = hypotheses[idx]["description"]
        print(f"\n✓ 已选择: {hypotheses[idx]['name']}")
    elif choice == "5":
        hypothesis = input("\n请输入你的研究假设: ").strip()
        if not hypothesis:
            print("✗ 假设不能为空")
            return
    else:
        print("✗ 无效选择，使用默认假设")
        hypothesis = hypotheses[0]["description"]

    print("\n即将生成因子，研究假设为：")
    print(f"  {hypothesis}")
    print()

    input("按回车键开始生成...")

    # 生成因子
    result = generate_factor_with_ai(hypothesis)

    if result is None:
        print("\n✗ 因子生成失败")
        return

    code, filepath = result

    # 显示代码
    display_generated_code(code)

    # 询问是否测试
    print()
    test_choice = input("是否测试生成的因子? (y/n): ").strip().lower()

    if test_choice == "y":
        test_generated_factor(filepath)

        # 总结
    print("\n" + "=" * 70)
    print("任务完成")
    print("=" * 70)
    print(f"""
✓ 因子代码已生成并保存

文件位置: {filepath.absolute()}

下一步:
1. 查看生成的代码，理解因子逻辑
2. 在真实数据上测试因子
3. 使用Qlib进行完整回测
4. 评估因子的IC、ICIR等指标
5. 如果效果好，可以部署到实盘

提示:
- 可以多次运行此脚本生成不同的因子
- 尝试不同的研究假设
- DeepSeek成本很低，可以多试验
- 保存有效的因子到你的因子库
""")
    print("=" * 70)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n✗ 用户中断")
    except Exception as e:
        print(f"\n✗ 程序出错: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

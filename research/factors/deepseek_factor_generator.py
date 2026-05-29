"""
DeepSeek 快速使用示例
展示如何使用 DeepSeek 进行量化因子生成
"""

import os

from dotenv import load_dotenv
from openai import OpenAI

# 加载环境变量
load_dotenv()


def generate_factor(description: str, save_to_file: bool = False):
    """
    使用 DeepSeek 生成量化因子

    Args:
        description: 因子描述
        save_to_file: 是否保存到文件
    """
    print(f"\n{'='*70}")
    print(f"生成因子: {description}")
    print(f"{'='*70}\n")

    # 初始化客户端
    client = OpenAI(
        api_key=os.getenv("DEEPSEEK_API_KEY"), base_url=os.getenv("DEEPSEEK_BASE_URL")
    )

    # 构建提示词
    prompt = f"""
作为一个量化分析师,请生成一个{description}的量化因子代码。

要求:
1. 使用 pandas 进行计算
2. 输入: DataFrame,包含 open, high, low, close, volume 列
3. 输出: Series,因子值
4. 包含完整的参数校验和错误处理
5. 添加详细的中文注释
6. 提供使用示例
7. 因子值进行标准化处理 (z-score)

代码示例格式:
```python
import pandas as pd
import numpy as np

def factor_name(df: pd.DataFrame, **params) -> pd.Series:
    '''因子说明'''
    # 实现代码
    return factor_series
```
"""

    print("⏳ 正在生成代码...")

    try:
        response = client.chat.completions.create(
            model="deepseek-coder",
            messages=[
                {
                    "role": "system",
                    "content": "你是一个专业的量化分析师,擅长编写高质量的因子代码。",
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=2000,
            temperature=0.3,
        )

        code = response.choices[0].message.content

        print("✓ 代码生成成功!\n")
        print(f"{'─'*70}")
        print(code)
        print(f"{'─'*70}")

        # 统计信息
        tokens = response.usage.total_tokens
        cost = tokens / 1000 * 0.001  # ¥0.001/1K tokens

        print("\n📊 统计信息:")
        print(f"  Token 使用: {tokens}")
        print(f"  成本: ¥{cost:.6f} (约{cost*1000:.3f}分)")

        # 保存到文件
        if save_to_file:
            filename = f"research/factors/generated_{description.replace(' ', '_')}.py"
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            with open(filename, "w", encoding="utf-8") as f:
                f.write(code)
            print(f"  已保存到: {filename}")

        return code

    except Exception as e:
        print(f"✗ 生成失败: {e}")
        return None


def main():
    print("=" * 70)
    print("DeepSeek 量化因子生成器")
    print("=" * 70)

    # 示例 1: 动量因子
    print("\n[示例 1] 生成动量因子")
    generate_factor("20日价格动量")

    # 示例 2: 波动率因子
    print("\n\n[示例 2] 生成波动率因子")
    generate_factor("历史波动率(ATR)")

    # 示例 3: 量价因子
    print("\n\n[示例 3] 生成量价因子")
    generate_factor("成交量加权平均价格(VWAP)")

    print("\n" + "=" * 70)
    print("✓ 所有示例完成!")
    print("=" * 70)

    print("\n🎯 下一步:")
    print("  1. 使用生成的因子进行回测")
    print("  2. 调整参数优化因子性能")
    print("  3. 组合多个因子构建策略")


if __name__ == "__main__":
    # 交互式使用
    print("\n" + "=" * 70)
    print("DeepSeek 量化因子生成器 - 交互模式")
    print("=" * 70)

    while True:
        print("\n请描述您想要的因子 (输入 'q' 退出, 'demo' 查看示例):")
        user_input = input("> ").strip()

        if user_input.lower() == "q":
            print("\n再见!")
            break
        elif user_input.lower() == "demo":
            main()
        elif user_input:
            save = input("是否保存到文件? (y/n): ").strip().lower() == "y"
            generate_factor(user_input, save_to_file=save)
        else:
            print("请输入因子描述")

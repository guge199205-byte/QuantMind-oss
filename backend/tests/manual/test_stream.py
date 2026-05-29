"""测试 OpenClaw 流式输出功能"""

import json

import requests


def test_stream(url, message, test_name):
    """测试流式端点"""
    print(f"\n{'='*60}")
    print(f"测试: {test_name}")
    print(f"消息: {message}")
    print(f"{'='*60}\n")

    payload = {"message": message, "user_id": "test_user"}

    try:
        response = requests.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
            stream=True,
            timeout=30,
        )

        if response.status_code != 200:
            print(f"❌ 错误: HTTP {response.status_code}")
            print(response.text)
            return False

        print("✅ 连接成功，开始接收流式响应:\n")

        for line in response.iter_lines():
            if line:
                line_str = line.decode("utf-8")
                if line_str.startswith("data: "):
                    data_str = line_str[6:]  # 去掉 'data: ' 前缀
                    try:
                        data = json.loads(data_str)

                        # 打印元数据
                        if data.get("type") == "meta":
                            print(f"📋 元数据: session_id={data.get('session_id')}")
                            print(f"   任务类型: {data.get('task_type')}")
                            if data.get("tasks"):
                                print(f"   创建任务: {data['tasks']}")
                            print()

                        # 打印回答片段
                        elif "answer" in data:
                            print(data["answer"], end="", flush=True)

                        # 完成标志
                        elif data.get("done"):
                            print("\n\n✅ 流式传输完成!")
                            if data.get("tasks"):
                                print(f"   后台任务: {len(data['tasks'])} 个")

                        # 错误
                        elif "error" in data:
                            print(f"\n❌ 错误: {data['error']}")
                            return False

                    except json.JSONDecodeError:
                        print(f"⚠️  无法解析: {data_str}")

        print(f"\n{'='*60}\n")
        return True

    except requests.exceptions.RequestException as e:
        print(f"❌ 请求失败: {e}")
        return False
    except KeyboardInterrupt:
        print("\n\n⚠️  测试被中断")
        return False


if __name__ == "__main__":
    base_url = "http://localhost:8015/api/openclaw/chat/stream"

    # 测试 1: 咨询类（千帆流式）
    test_stream(base_url, "请分析一下贵州茅台的基本面", "咨询类任务（千帆流式）")

    # 测试 2: 账户查询（本地任务）
    test_stream(base_url, "查询我的持仓", "账户查询（本地任务 + Qwen）")

    # 测试 3: 交易任务
    test_stream(base_url, "买入600519贵州茅台100股", "交易执行（本地任务 + Qwen）")

    print("\n✅ 所有测试完成！")

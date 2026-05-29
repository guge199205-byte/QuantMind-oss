"""简化测试 - 仅测试创建会话"""

import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

# 加载环境变量
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(env_path, override=True)

token = os.getenv("APPBUILDER_TOKEN")
app_id = os.getenv("APPBUILDER_APP_ID")

print("=" * 60)
print("千帆 API 创建会话测试")
print("=" * 60)
print(f"\nToken: {token[:50]}..." if token else "Token: 未配置")
print(f"App ID: {app_id}")

url = "https://qianfan.baidubce.com/v2/app/conversation"
headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
payload = {"app_id": app_id}

print("\n发起请求:")
print(f"  URL: {url}")
print(f"  Headers: {json.dumps({k: v[:50]+'...' if k=='Authorization' else v for k,v in headers.items()}, indent=4)}")
print(f"  Payload: {json.dumps(payload, indent=4)}")

try:
    response = requests.post(url, headers=headers, json=payload, timeout=10)

    print("\n响应:")
    print(f"  状态码: {response.status_code}")
    print(f"  响应头: {dict(response.headers)}")
    print(f"  响应体:\n{response.text}")

    if response.status_code == 200:
        data = response.json()
        print(f"\n✅ 成功! 会话ID: {data.get('conversation_id')}")
    else:
        print("\n❌ 失败!")
        try:
            error_data = response.json()
            print(f"  错误详情: {json.dumps(error_data, indent=4, ensure_ascii=False)}")
        except:
            pass

except Exception as e:
    print(f"\n❌ 异常: {e}")
    import traceback

    traceback.print_exc()

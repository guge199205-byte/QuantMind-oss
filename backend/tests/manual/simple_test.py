"""简化的单次测试"""

import json

import requests

url = "http://localhost:8015/api/openclaw/chat/stream"
payload = {"message": "买入600519贵州茅台100股", "user_id": "test_user"}

print("发送请求:", payload)
print("\n开始接收响应:\n" + "=" * 60)

response = requests.post(url, json=payload, stream=True, timeout=10)

for line in response.iter_lines():
    if line:
        line_str = line.decode("utf-8")
        if line_str.startswith("data: "):
            data = json.loads(line_str[6:])
            if "answer" in data:
                print(data["answer"], end="", flush=True)
            elif data.get("type") == "meta":
                print(f"\n元数据: {json.dumps(data, ensure_ascii=False)}\n")
            elif data.get("done"):
                print(f"\n\n完成! {json.dumps(data, ensure_ascii=False)}")

print("\n" + "=" * 60)

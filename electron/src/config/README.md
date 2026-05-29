# config

用途：配置与环境参数。

## 说明
- 归属路径：electron\src\config
- 修改本目录代码后请同步更新本 README

## COS 绝对地址配置

- 默认公有读地址统一为：`https://cos.quantmind.cloud`
- 读取优先级：
  1. `TENCENT_COS_URL`
  2. `VITE_TENCENT_COS_URL`
  3. 默认值 `https://cos.quantmind.cloud`
- 说明：上传写入仍可使用私有写凭证（SecretId/SecretKey + Bucket/Region），返回给前端展示与存储的读取 URL 统一使用绝对地址。

## 页面壳统一配置

- `pageLayout.ts` 统一管理 Electron 页面外壳边距与容器节奏：
  - 外层背景与窗口留白（当前统一为 `p-6`）
  - 白色 frame 容器
  - 顶部标题栏高度
  - 左侧导航宽度
  - 面包屑与内容区 padding
- 回测中心与模型训练模块应优先复用这份配置，避免不同页面出现不一致的边距和容器圆角。

## 更新记录
- 2026-03-29：`backtest.ts` 中 TopkDropout 默认参数调整为 20% 调仓比例（`topk=50, n_drop=10`）。

## 安全说明

- 前端代码中不再内置任何 COS Secret（`SecretId/SecretKey`），必须通过环境变量注入。
- 若未注入写入凭证，`enabled` 将为 `false`；仅依赖公有读域名的展示链路不受影响。

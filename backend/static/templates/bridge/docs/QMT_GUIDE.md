# QMT Bridge 接入指引 (极简版)

为了让您的 QMT 客户端能够接收来自 QuantMind 的交易指令，请完成以下手动配置步骤：

### 1. 软件环境
*   请确保安装了 **Python 3.7+**。
*   在您的 Python 环境中运行：
    ```bash
    pip install websocket-client xtquant
    ```

### 2. 获取 QMT 本地路径
*   打开 QMT 客户端，进入“极简模式”。
*   找到您的 **userdata_mini** 文件夹路径。默认情况下通常在 QMT 安装目录的 `userdata_mini` 文件夹中。
*   **修改脚本**：将脚本顶部的 `QMT_PATH` 修改为您电脑上的实际路径。
    *   *示例*：`QMT_PATH = r"D:\QMT\userdata_mini"` (注意前面的 `r` 不能删除)。

### 3. 获取 Session ID
*   QMT 每个运行实例通常会分配一个唯一的 Session ID，默认为 `123456`。
*   如果无法连接，请查阅 QMT “极简版助手”或联系券商确认当前的 Session ID。
*   **修改脚本**：将脚本顶部的 `QMT_SESSION_ID` 修改为正确的值。

### 4. 获取资金账号
*   在 QMT 界面查看您的 8 位或更多位的资金账号。
*   **修改脚本**：将 `QMT_ACCOUNT_ID` 修改为您的真实账号。

### 5. 运行与验证
*   在本地 IDE 或 CMD 中运行 `python qmt_bridge.py`。
*   看到 `[System] QMT 终端连接成功` 和 `[System] 正在连接云端网关` 即表示连接成功。

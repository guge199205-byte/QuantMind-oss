# OpenVPN 客户端部署指南

此目录包含使用 Docker 部署 OpenVPN 客户端的配置。

## 部署步骤

1. **准备配置文件**
   将您的 `.ovpn` 配置文件（及其依赖的证书/密钥文件）放入 `vpn/` 目录中。
   确保文件名以 `.ovpn` 结尾。

   ```bash
   # 示例：将配置文件复制到 vpn 目录
   cp /path/to/your-config.ovpn ./vpn/
   ```

2. **启动 VPN 客户端**
   在当前目录下运行：

   ```bash
   docker-compose up -d
   ```

3. **验证连接**
   查看日志以确认连接成功：

   ```bash
   docker logs -f quantmind-vpn-client
   ```

   如果看到 `Initialization Sequence Completed`，说明连接成功。

## 使用方式

### 方式一：HTTP 代理 (推荐)
该容器内置了 Privoxy HTTP 代理，监听端口 `8118`。
其他服务可以通过设置 HTTP 代理使用 VPN 网络：

- **HTTP_PROXY**: `http://quantmind-vpn-client:8118`
- **HTTPS_PROXY**: `http://quantmind-vpn-client:8118`

### 方式二：容器网络共享
让其他容器直接使用 VPN 容器的网络栈（注意：这会使该容器与 VPN 容器共享 IP，端口映射需在 VPN 容器上配置）：

```yaml
services:
  some-service:
    network_mode: "service:vpn-client"
    # ...
```

## 注意事项

- 需要 `NET_ADMIN` 权限和 `/dev/net/tun` 设备映射。
- 默认启用了 HTTP 代理 (Privoxy)以便于其他服务连接。
- 配置文件中的路径如果是绝对路径，请修改为相对路径或 `/vpn/` 下的路径。

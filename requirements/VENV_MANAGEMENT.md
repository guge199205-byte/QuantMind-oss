# 虚拟环境管理指南

## 📁 当前结构（遵循AGENTS.md架构）

### 根目录共享环境
```
.venv/ (977MB) - 用于开发、测试、脚本运行
```

### 服务独立环境
每个后端服务使用独立虚拟环境，确保依赖隔离和数据隔离：

```
backend/
├── api_gateway/.venv (395MB)
├── user_service/.venv (113MB)
├── portfolio_service/.venv (234MB)
├── trading_service/.venv (重建中)
├── simulation_service/.venv (71MB)
├── strategy_service/.venv (222MB)
├── market_data_service/.venv (103MB)
├── ai_strategy/.venv (重建完成，87包)
├── ai_inference/.venv (重建中)
├── ai_ide_service/.venv (259MB)
├── admin_service/.venv (343MB)
├── community/.venv (581MB)
└── qlib_service/.venv (重建中)
```

---

## 🎯 管理原则

### 1. 独立环境原则
**为什么需要独立环境？**
- ✅ 依赖隔离：不同服务可能需要不同版本的库
- ✅ 数据隔离：多租户环境下确保数据不冲突
- ✅ 安全隔离：一个服务的漏洞不影响其他服务
- ✅ 可维护性：便于单独升级、测试、部署

### 2. 环境命名规范
```bash
# 统一使用 .venv 目录名
<service_dir>/.venv/

# ❌ 错误示范
venv310/
venv_ai/
env/
```

### 3. 生产环境依赖
所有服务虚拟环境应使用：
```bash
pip install -r requirements/production.txt
```

---

## 🔧 服务虚拟环境创建

### 标准流程
```bash
# 1. 进入服务目录
cd backend/<service_name>

# 2. 创建虚拟环境（Python 3.10+）
python3.10 -m venv .venv

# 3. 激活环境
source .venv/bin/activate  # Mac/Linux
.venv\Scripts\activate     # Windows

# 4. 升级pip
pip install --upgrade pip

# 5. 安装生产依赖
pip install -r ../../requirements/production.txt

# 6. 验证安装
pip list
python -c "import fastapi, sqlalchemy; print('✅ 核心依赖正常')"
```

### 快速重建脚本
```bash
#!/bin/bash
# rebuild_service_venv.sh
SERVICE=$1
cd backend/$SERVICE
rm -rf .venv
python3.10 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r ../../requirements/production.txt
echo "✅ $SERVICE 虚拟环境已重建"
```

---

## 📊 环境维护

### 定期检查（每月）
```bash
# 检查所有服务环境大小
du -sh backend/*/.venv | sort -hr

# 识别空环境（<50MB）
for dir in backend/*/.venv; do
  size=$(du -sm "$dir" 2>/dev/null | awk '{print $1}')
  if [ "$size" -lt 50 ]; then
    echo "⚠️  $dir 可能是空环境 ($size MB)"
  fi
done
```

### 清理策略
```bash
# ❌ 不要删除：正常使用的服务环境（>50MB）
# ✅ 可以删除：空环境（<50MB）且确认服务不活跃
# ✅ 可以删除：临时测试环境（.test_venv, venv_test等）
```

---

## 🐳 Docker环境

### 容器内虚拟环境
Docker容器内**不需要**虚拟环境，因为容器本身就是隔离环境：
```dockerfile
# ❌ 不推荐（冗余隔离）
RUN python -m venv /app/venv

# ✅ 推荐（直接安装到系统Python）
RUN pip install -r requirements/production.txt
```

### 多阶段构建例外
仅在多阶段构建时使用虚拟环境：
```dockerfile
# Stage 1: Builder
RUN python -m venv /opt/venv
RUN /opt/venv/bin/pip install -r production.txt

# Stage 2: Runtime
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
```

---

## ⚠️ 常见问题

### Q1: 为什么某些服务环境只有19MB？
**A**: 可能是：
1. 刚创建还未安装依赖
2. 安装失败
3. 被错误清理

**解决**: 重新安装依赖
```bash
cd backend/<service>
source .venv/bin/activate
pip install -r ../../requirements/production.txt
```

### Q2: 所有服务都需要独立环境吗？
**A**: 是的。根据AGENTS.md架构要求，每个后端服务必须使用独立虚拟环境。

### Q3: 虚拟环境占用太多空间怎么办？
**A**: 
1. 使用 `requirements/production.txt`（42行）而非完整依赖
2. 删除不活跃服务的虚拟环境
3. 考虑使用Docker部署（容器内不需要虚拟环境）

### Q4: 根目录.venv的作用？
**A**: 用于：
- 运行跨服务脚本（如测试、数据处理）
- 开发环境的统一工具链（black, pytest等）
- CI/CD流程

---

## 📋 检查清单

### 新服务上线
- [ ] 创建服务目录下的 `.venv`
- [ ] 安装 `production.txt` 依赖
- [ ] 验证核心模块导入
- [ ] 更新服务 `README.md` 说明环境要求
- [ ] 添加到 `.gitignore`

### 依赖更新
- [ ] 更新 `requirements/production.txt`
- [ ] 在根目录测试安装
- [ ] 逐个服务更新虚拟环境
- [ ] 运行测试验证兼容性

### 定期维护
- [ ] 每月检查环境大小
- [ ] 清理空环境
- [ ] 更新过时依赖
- [ ] 运行安全扫描

---

## 📚 相关文档
- `AGENTS.md` - 架构要求和开发规范
- `requirements/production.txt` - 生产依赖
- `requirements/dev.txt` - 开发依赖
- `requirements/OPTIMIZATION_SUMMARY.md` - 依赖优化说明

---

**维护负责人**: QuantMind Team  
**最后更新**: 2026-02-16

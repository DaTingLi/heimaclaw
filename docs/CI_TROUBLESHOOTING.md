# CI/CD 问题排查指南

**版本**: v1.0  
**创建日期**: 2026-03-19

---

## 常见 CI 错误及解决方案

### 1. Ruff Import 排序错误

**错误**：
```
I001 Import block is un-sorted or un-formatted
```

**原因**：import 语句未按字母顺序排列

**解决**：
```bash
ruff check --fix src/
```

---

### 2. Black 行太长

**错误**：
```
E501 Line too long (105 > 88)
```

**原因**：代码行超过 88 字符

**解决**：拆分长行
```python
# 错误
error("飞书未配置，请先运行: heimaclaw config set channels.feishu.accounts.default.app_id <APP_ID>")

# 正确
error(
    "飞书未配置，请先运行: "
    "heimaclaw config set channels.feishu.accounts.default.app_id <APP_ID>"
)
```

---

### 3. 空白行有空格

**错误**：
```
W293 Blank line contains whitespace
```

**原因**：空白行包含空格或制表符

**解决**：
```bash
# 删除空白行的多余空格
sed -i '/^[[:space:]]*$/d' 文件.py
# 或使用 ruff --fix
ruff check --fix src/
```

---

### 4. 循环导入

**错误**：
```
ImportError: cannot import name 'get_tool_registry' from partially initialized module
```

**原因**：
- `tools/__init__.py` 导入 `exec_tool.py`
- `exec_tool.py` 又导入 `tools/__init__.py`

**解决**：延迟导入
```python
# tools/__init__.py
def get_tool_registry():
    # 延迟导入，避免循环
    from heimaclaw.agent.tools.registry import ToolRegistry
    return _registry
```

---

### 5. Python 版本不兼容

**错误**：
```
Warning: Python 3.10 cannot parse code formatted for Python 3.14
```

**原因**：Black 使用了更高版本的 Python 格式化

**解决**：
```bash
# 使用 --target-version
black --target-version py310 src/
```

---

## CI 检查流程

在推送代码前，在本地运行：

```bash
# 1. Ruff 检查
ruff check src/ tests/

# 2. Black 格式化
black --target-version py310 src/ tests/

# 3. 类型检查
mypy src/heimaclaw --ignore-missing-imports

# 4. 测试
pytest tests/ -v

# 5. 完整 CI 模拟
./scripts/ci.sh
```

---

## Git Hooks（推荐）

添加 pre-commit hook 自动检查：

```bash
# .git/hooks/pre-commit
#!/bin/bash
set -e

echo "Running pre-commit checks..."

# Ruff
ruff check src/ tests/ --fix

# Black
black --target-version py310 src/ tests/

# Pytest
pytest tests/ -q

echo "All checks passed!"
```

---

## 本地 CI 验证

每次推送前，在本地完整运行 CI 检查：

```bash
# 模拟 CI 环境
cd /root/dt/ai_coding/heimaclaw
/root/miniconda3/envs/heimaclaw/bin/python -m pytest tests/ -q
/root/miniconda3/envs/heimaclaw/bin/ruff check src/ tests/
/root/miniconda3/envs/heimaclaw/bin/black --target-version py310 --check src/ tests/
```

---

## 常用命令

```bash
# 检查单个文件
ruff check src/heimaclaw/cli.py

# 自动修复
ruff check --fix src/

# 检查并格式化
black --target-version py310 src/

# 查看详细错误
ruff check src/ -v
```

---

_文档创建: 2026-03-19_

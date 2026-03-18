"""
HeiMaClaw CLI 入口模块

提供所有命令行接口，包括：
- heimaclaw --help
- heimaclaw init
- heimaclaw start
- heimaclaw status
- heimaclaw doctor
- heimaclaw config show/set/edit
- heimaclaw channel setup
- heimaclaw agent create
"""

from pathlib import Path
from typing import Any, Optional

import typer
from rich.table import Table

from heimaclaw import __version__
from heimaclaw.console import (
    console,
    error,
    info,
    print_panel,
    print_table,
    success,
    title,
    warning,
)

# 创建主应用
app = typer.Typer(
    name="heimaclaw",
    help="HeiMaClaw - 生产级企业 AI Agent 平台",
    add_completion=False,
    no_args_is_help=True,
)

# 创建子命令组
config_app = typer.Typer(help="配置管理命令")
agent_app = typer.Typer(help="Agent 管理命令")
channel_app = typer.Typer(help="渠道配置命令")

# 注册子命令组
app.add_typer(config_app, name="config")
app.add_typer(agent_app, name="agent")
app.add_typer(channel_app, name="channel")


def version_callback(value: bool) -> None:
    """显示版本信息"""
    if value:
        print_panel(f"HeiMaClaw v{__version__}", title_str="版本", style="cyan")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        help="显示版本信息",
        callback=version_callback,
        is_eager=True,
    ),
) -> None:
    """
    HeiMaClaw - 生产级企业 AI Agent 平台

    每个 Agent 运行在独立 microVM 中，实现硬件级隔离。
    支持飞书和企业微信双渠道。
    """
    pass


# ==================== init 命令 ====================


@app.command("init")
def init_command(
    path: Optional[str] = typer.Option(
        None,
        "--path",
        "-p",
        help="项目初始化路径，默认为 /opt/heimaclaw",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="强制覆盖已存在的配置",
    ),
) -> None:
    """
    初始化 HeiMaClaw 项目

    创建必要的目录结构和默认配置文件。
    """
    from pathlib import Path

    project_path = Path(path) if path else Path("/opt/heimaclaw")

    title(f"初始化 HeiMaClaw 项目: {project_path}")

    # 检查目录是否存在
    if project_path.exists() and not force:
        warning(f"目录已存在: {project_path}")
        if not typer.confirm("是否继续？"):
            raise typer.Abort()

    # 创建目录结构
    directories = [
        "config",
        "logs",
        "data",
        "sandboxes",
        "data/agents",
        "data/sessions",
    ]

    for dir_name in directories:
        dir_path = project_path / dir_name
        dir_path.mkdir(parents=True, exist_ok=True)
        info(f"  创建目录: {dir_name}")

    # 创建默认配置文件
    config_path = project_path / "config" / "config.toml"
    if not config_path.exists() or force:
        _create_default_config(config_path)
        success("  创建配置: config/config.toml")
    else:
        warning("  配置已存在，跳过: config/config.toml")

    success(f"初始化完成: {project_path}")
    info("下一步: 运行 'heimaclaw config show' 查看配置")


def _create_default_config(config_path: "Path") -> None:
    """创建默认配置文件"""
    import tomli_w

    default_config = {
        "heimaclaw": {
            "name": "HeiMaClaw",
            "version": __version__,
            "environment": "development",
        },
        "server": {
            "host": "0.0.0.0",
            "port": 8000,
            "workers": 1,
        },
        "sandbox": {
            "enabled": True,
            "backend": "firecracker",
            "warm_pool_size": 5,
            "max_instances": 100,
            "memory_mb": 128,
            "cpu_count": 1,
        },
        "channels": {
            "feishu": {
                "enabled": False,
                "app_id": "",
                "app_secret": "",
            },
            "wecom": {
                "enabled": False,
                "corp_id": "",
                "agent_id": "",
                "secret": "",
            },
        },
        "logging": {
            "level": "INFO",
            "file_enabled": True,
            "file_path": "logs/heimaclaw.log",
            "console_enabled": True,
        },
    }

    with open(config_path, "wb") as f:
        tomli_w.dump(default_config, f)


# ==================== start 命令 ====================


@app.command("start")
def start_command(
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="监听地址"),
    port: int = typer.Option(8000, "--port", "-p", help="监听端口"),
    workers: int = typer.Option(1, "--workers", "-w", help="工作进程数"),
    reload: bool = typer.Option(False, "--reload", help="开发模式自动重载"),
) -> None:
    """
    启动 HeiMaClaw 服务

    启动 FastAPI 服务，监听飞书和企业微信的 webhook 回调。
    """
    import uvicorn

    title("启动 HeiMaClaw 服务")

    info(f"监听地址: {host}:{port}")
    info(f"工作进程: {workers}")

    if reload:
        warning("开发模式已启用，代码变更将自动重载")

    try:
        uvicorn.run(
            "heimaclaw.server:app",
            host=host,
            port=port,
            workers=workers if not reload else 1,
            reload=reload,
        )
    except KeyboardInterrupt:
        info("服务已停止")
    except Exception as e:
        error(f"启动失败: {e}")
        raise typer.Exit(1)


# ==================== status 命令 ====================


@app.command("status")
def status_command() -> None:
    """
    显示 HeiMaClaw 运行状态

    包括服务状态、Agent 数量、沙箱池状态等。
    """
    title("HeiMaClaw 状态")

    # 服务状态
    table = Table(title="服务状态", show_header=True, header_style="cyan bold")
    table.add_column("项目")
    table.add_column("状态")
    table.add_column("详情")

    table.add_row("服务", "[yellow]未启动[/yellow]", "-")
    table.add_row("沙箱后端", "[yellow]未初始化[/yellow]", "-")
    table.add_row("预热池", "[dim]0 / 5[/dim]", "-")
    table.add_row("活跃 Agent", "[dim]0[/dim]", "-")
    table.add_row("活跃会话", "[dim]0[/dim]", "-")

    console.print(table)

    # 渠道状态
    channel_table = Table(title="渠道状态", show_header=True, header_style="cyan bold")
    channel_table.add_column("渠道")
    channel_table.add_column("状态")
    channel_table.add_column("配置")

    channel_table.add_row("飞书", "[yellow]未配置[/yellow]", "-")
    channel_table.add_row("企业微信", "[yellow]未配置[/yellow]", "-")

    console.print(channel_table)


# ==================== doctor 命令 ====================


@app.command("doctor")
def doctor_command() -> None:
    """
    诊断 HeiMaClaw 运行环境

    检查系统依赖、配置、权限等是否正确。
    """
    import platform
    import shutil
    from pathlib import Path

    title("HeiMaClaw 环境诊断")

    checks = []

    # Python 版本检查
    py_version = platform.python_version()
    py_ok = tuple(map(int, py_version.split("."))) >= (3, 11, 0)
    checks.append(
        (
            "Python 版本",
            "[green]OK[/green]" if py_ok else "[red]需要 3.11+[/red]",
            py_version,
        )
    )

    # KVM 支持检查
    kvm_path = Path("/dev/kvm")
    if kvm_path.exists():
        kvm_ok = kvm_path.is_char_device()
        checks.append(
            (
                "KVM 支持",
                "[green]OK[/green]" if kvm_ok else "[red]不可用[/red]",
                "硬件虚拟化已启用",
            )
        )
    else:
        checks.append(
            (
                "KVM 支持",
                "[yellow]未检测到[/yellow]",
                "沙箱将使用降级模式",
            )
        )

    # Firecracker 检查
    fc_path = shutil.which("firecracker")
    checks.append(
        (
            "Firecracker",
            "[green]OK[/green]" if fc_path else "[yellow]未安装[/yellow]",
            fc_path or "需要安装",
        )
    )

    # 配置文件检查
    config_path = Path("/opt/heimaclaw/config/config.toml")
    if not config_path.exists():
        config_path = Path.home() / ".heimaclaw" / "config.toml"
    checks.append(
        (
            "配置文件",
            "[green]OK[/green]" if config_path.exists() else "[yellow]未创建[/yellow]",
            str(config_path) if config_path.exists() else "运行 'heimaclaw init'",
        )
    )

    # 端口检查
    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(("0.0.0.0", 8000))
    sock.close()
    port_ok = result != 0
    checks.append(
        (
            "端口 8000",
            "[green]可用[/green]" if port_ok else "[yellow]已被占用[/yellow]",
            "服务默认端口",
        )
    )

    # 打印结果
    print_table("诊断结果", [list(c) for c in checks], ["检查项", "状态", "详情"])

    # 计算健康度
    ok_count = sum(1 for c in checks if "[green]" in c[1])
    total = len(checks)

    if ok_count == total:
        success(f"环境检查通过: {ok_count}/{total}")
    else:
        warning(f"部分检查未通过: {ok_count}/{total}")


# ==================== config 子命令 ====================


@config_app.command("show")
def config_show(
    key: Optional[str] = typer.Argument(None, help="配置键名，如 server.port"),
) -> None:
    """
    显示当前配置

    不指定 key 则显示全部配置。
    """
    from pathlib import Path

    title("配置信息")

    config_path = Path("/opt/heimaclaw/config/config.toml")
    if not config_path.exists():
        config_path = Path.home() / ".heimaclaw" / "config.toml"

    if not config_path.exists():
        error("配置文件不存在，请先运行 'heimaclaw init'")
        raise typer.Exit(1)

    import tomli

    with open(config_path, "rb") as f:
        config = tomli.load(f)

    if key:
        # 显示指定键
        keys = key.split(".")
        value = config
        try:
            for k in keys:
                value = value[k]
            console.print(f"[cyan]{key}[/cyan] = [green]{value}[/green]")
        except KeyError:
            error(f"配置键不存在: {key}")
            raise typer.Exit(1)
    else:
        # 显示全部配置
        import json

        config_json = json.dumps(config, indent=2, ensure_ascii=False)
        print_panel(config_json, title_str="当前配置", style="cyan")


@config_app.command("set")
def config_set(
    key: str = typer.Argument(..., help="配置键名，如 server.port"),
    value: str = typer.Argument(..., help="配置值"),
) -> None:
    """
    设置配置项

    示例: heimaclaw config set server.port 8080
    """
    from pathlib import Path

    config_path = Path("/opt/heimaclaw/config/config.toml")
    if not config_path.exists():
        config_path = Path.home() / ".heimaclaw" / "config.toml"

    if not config_path.exists():
        error("配置文件不存在，请先运行 'heimaclaw init'")
        raise typer.Exit(1)

    import tomli
    import tomli_w

    with open(config_path, "rb") as f:
        config = tomli.load(f)

    # 解析键路径并设置值
    keys = key.split(".")
    current = config
    for k in keys[:-1]:
        if k not in current:
            current[k] = {}
        current = current[k]

    # 尝试转换值类型
    parsed_value: Any = value
    try:
        if value.lower() == "true":
            parsed_value = True
        elif value.lower() == "false":
            parsed_value = False
        elif value.isdigit():
            parsed_value = int(value)
        elif value.replace(".", "").isdigit():
            parsed_value = float(value)
        else:
            parsed_value = value
    except Exception:
        parsed_value = value

    current[keys[-1]] = parsed_value

    with open(config_path, "wb") as f:
        tomli_w.dump(config, f)

    success(f"已设置: {key} = {parsed_value}")


@config_app.command("edit")
def config_edit() -> None:
    """
    使用编辑器编辑配置文件

    使用 EDITOR 环境变量指定的编辑器，默认使用 nano。
    """
    import os
    import subprocess
    from pathlib import Path

    config_path = Path("/opt/heimaclaw/config/config.toml")
    if not config_path.exists():
        config_path = Path.home() / ".heimaclaw" / "config.toml"

    if not config_path.exists():
        error("配置文件不存在，请先运行 'heimaclaw init'")
        raise typer.Exit(1)

    editor = os.getenv("EDITOR", "nano")

    try:
        subprocess.run([editor, str(config_path)], check=True)
        success("配置已更新")
    except subprocess.CalledProcessError:
        error("编辑器退出异常")
        raise typer.Exit(1)
    except FileNotFoundError:
        error(f"编辑器不存在: {editor}")
        raise typer.Exit(1)


# ==================== agent 子命令 ====================


@agent_app.command("create")
def agent_create(
    name: str = typer.Argument(..., help="Agent 名称"),
    channel: str = typer.Option(
        "feishu",
        "--channel",
        "-c",
        help="渠道类型: feishu / wecom",
    ),
    description: str = typer.Option(
        "",
        "--description",
        "-d",
        help="Agent 描述",
    ),
) -> None:
    """
    创建新的 Agent

    创建一个独立的 Agent 配置和运行环境。
    """
    import json
    from pathlib import Path

    if channel not in ("feishu", "wecom"):
        error(f"不支持的渠道类型: {channel}")
        raise typer.Exit(1)

    title(f"创建 Agent: {name}")

    # Agent 配置目录
    agents_dir = Path("/opt/heimaclaw/data/agents")
    if not agents_dir.exists():
        agents_dir = Path.home() / ".heimaclaw" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)

    agent_dir = agents_dir / name

    if agent_dir.exists():
        error(f"Agent 已存在: {name}")
        raise typer.Exit(1)

    agent_dir.mkdir(parents=True)

    # 创建 Agent 配置
    agent_config = {
        "name": name,
        "description": description,
        "channel": channel,
        "enabled": True,
        "sandbox": {
            "enabled": True,
            "memory_mb": 128,
            "cpu_count": 1,
        },
        "model": {
            "provider": "openai",
            "model_name": "gpt-4",
            "api_key": "",
        },
        "tools": [],
        "created_at": None,  # 运行时填充
    }

    config_file = agent_dir / "agent.json"
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(agent_config, f, indent=2, ensure_ascii=False)

    success(f"Agent 创建成功: {name}")
    info(f"配置文件: {config_file}")
    info(f"下一步: 编辑配置并运行 'heimaclaw channel setup {channel}'")


@agent_app.command("list")
def agent_list() -> None:
    """
    列出所有 Agent
    """
    import json
    from pathlib import Path

    title("Agent 列表")

    agents_dir = Path("/opt/heimaclaw/data/agents")
    if not agents_dir.exists():
        agents_dir = Path.home() / ".heimaclaw" / "agents"

    if not agents_dir.exists():
        info("暂无 Agent")
        return

    agents = []
    for agent_dir in agents_dir.iterdir():
        if agent_dir.is_dir():
            config_file = agent_dir / "agent.json"
            if config_file.exists():
                with open(config_file, encoding="utf-8") as f:
                    config = json.load(f)
                agents.append(
                    [
                        config.get("name", agent_dir.name),
                        config.get("channel", "-"),
                        "[green]启用[/green]"
                        if config.get("enabled")
                        else "[dim]禁用[/dim]",
                        config.get("description", "-")[:30],
                    ]
                )

    if agents:
        print_table("Agent 列表", agents, ["名称", "渠道", "状态", "描述"])
    else:
        info("暂无 Agent")


# ==================== channel 子命令 ====================


@channel_app.command("setup")
def channel_setup(
    channel: str = typer.Argument(..., help="渠道类型: feishu / wecom"),
) -> None:
    """
    配置渠道

    交互式引导配置飞书或企业微信。
    """
    if channel not in ("feishu", "wecom"):
        error(f"不支持的渠道类型: {channel}")
        raise typer.Exit(1)

    title(f"配置渠道: {channel}")

    if channel == "feishu":
        _setup_feishu()
    else:
        _setup_wecom()


def _setup_feishu() -> None:
    """配置飞书渠道"""
    info("飞书配置向导")
    info("")
    info("请准备以下信息:")
    info("  1. 飞书开放平台应用 App ID")
    info("  2. 飞书开放平台应用 App Secret")
    info("")

    typer.prompt("请输入 App ID")
    typer.prompt("请输入 App Secret", hide_input=True)

    # 生成回调 URL
    callback_url = "https://your-domain.com/webhook/feishu"

    info("")
    success("配置完成!")
    info(f"回调 URL: {callback_url}")
    info("")
    info("下一步:")
    info("  1. 将回调 URL 配置到飞书开放平台")
    info("  2. 运行 'heimaclaw start' 启动服务")


def _setup_wecom() -> None:
    """配置企业微信渠道"""
    info("企业微信配置向导")
    info("")
    info("请准备以下信息:")
    info("  1. 企业 ID (Corp ID)")
    info("  2. 应用 Agent ID")
    info("  3. 应用 Secret")
    info("")

    typer.prompt("请输入企业 ID")
    typer.prompt("请输入应用 Agent ID")
    typer.prompt("请输入应用 Secret", hide_input=True)

    # 生成回调 URL
    callback_url = "https://your-domain.com/webhook/wecom"

    info("")
    success("配置完成!")
    info(f"回调 URL: {callback_url}")
    info("")
    info("下一步:")
    info("  1. 将回调 URL 配置到企业微信管理后台")
    info("  2. 运行 'heimaclaw start' 启动服务")


if __name__ == "__main__":
    app()


# ==================== tool 子命令 ====================

tool_app = typer.Typer(help="工具管理命令")
app.add_typer(tool_app, name="tool")


@tool_app.command("install")
def tool_install(
    source: str = typer.Argument(..., help="工具源（本地路径/Git URL/PyPI 包名）"),
) -> None:
    """
    安装工具

    支持三种安装方式：
    - 本地目录: heimaclaw tool install /path/to/tool
    - Git 仓库: heimaclaw tool install https://github.com/xxx/tool
    - PyPI 包: heimaclaw tool install heimaclaw-tool-xxx
    """
    from heimaclaw.tool.manager import get_tool_manager

    manager = get_tool_manager()
    success = manager.install(source)

    if not success:
        raise typer.Exit(1)


@tool_app.command("uninstall")
def tool_uninstall(
    name: str = typer.Argument(..., help="工具名称"),
) -> None:
    """
    卸载工具
    """
    from heimaclaw.tool.manager import get_tool_manager

    manager = get_tool_manager()
    success = manager.uninstall(name)

    if not success:
        raise typer.Exit(1)


@tool_app.command("list")
def tool_list() -> None:
    """
    列出已安装的工具
    """
    from rich.table import Table

    from heimaclaw.tool.manager import get_tool_manager

    manager = get_tool_manager()
    tools = manager.list()

    table = Table(title="已安装工具", show_header=True, header_style="cyan bold")
    table.add_column("名称")
    table.add_column("版本")
    table.add_column("描述")
    table.add_column("函数数")
    table.add_column("状态")

    for tool in tools:
        status = "[green]启用[/green]" if tool.enabled else "[dim]禁用[/dim]"
        table.add_row(
            tool.name,
            tool.version,
            tool.description[:30] + "..."
            if len(tool.description) > 30
            else tool.description,
            str(len(tool.functions)),
            status,
        )

    if not tools:
        info("暂无已安装的工具")
    else:
        console.print(table)


@tool_app.command("info")
def tool_info(
    name: str = typer.Argument(..., help="工具名称"),
) -> None:
    """
    显示工具详细信息
    """

    from heimaclaw.tool.manager import get_tool_manager

    manager = get_tool_manager()
    tool = manager.get(name)

    if not tool:
        error(f"工具不存在: {name}")
        raise typer.Exit(1)

    # 显示工具信息
    info_text = f"""名称: {tool.name}
版本: {tool.version}
路径: {tool.path}
状态: {"启用" if tool.enabled else "禁用"}

描述:
{tool.description}

函数列表:"""

    for func in tool.functions:
        info_text += (
            f"\n  - {func.get('name', 'unknown')}: {func.get('description', '')}"
        )

    print_panel(info_text, title_str=f"工具信息: {name}")


@tool_app.command("enable")
def tool_enable(
    name: str = typer.Argument(..., help="工具名称"),
) -> None:
    """启用工具"""
    from heimaclaw.tool.manager import get_tool_manager

    manager = get_tool_manager()
    if manager.enable(name):
        success(f"已启用工具: {name}")
    else:
        error(f"工具不存在: {name}")
        raise typer.Exit(1)


@tool_app.command("disable")
def tool_disable(
    name: str = typer.Argument(..., help="工具名称"),
) -> None:
    """禁用工具"""
    from heimaclaw.tool.manager import get_tool_manager

    manager = get_tool_manager()
    if manager.disable(name):
        success(f"已禁用工具: {name}")
    else:
        error(f"工具不存在: {name}")
        raise typer.Exit(1)


@tool_app.command("create")
def tool_create(
    name: str = typer.Argument(..., help="工具名称"),
    path: str = typer.Option(".", "--path", "-p", help="创建路径"),
) -> None:
    """
    创建工具模板

    创建一个新的工具包模板，包含必要的文件结构。
    """
    import json
    from pathlib import Path

    tool_dir = Path(path) / f"heimaclaw-tool-{name}"

    if tool_dir.exists():
        error(f"目录已存在: {tool_dir}")
        raise typer.Exit(1)

    tool_dir.mkdir(parents=True)

    # 创建 tool.json
    tool_json = {
        "name": name,
        "version": "1.0.0",
        "description": f"{name} 工具",
        "entry": "main.py",
        "functions": [
            {
                "name": f"{name}_example",
                "description": "示例函数",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "input": {"type": "string", "description": "输入参数"}
                    },
                    "required": ["input"],
                },
                "timeout_ms": 5000,
            }
        ],
    }

    with open(tool_dir / "tool.json", "w", encoding="utf-8") as f:
        json.dump(tool_json, f, indent=2, ensure_ascii=False)

    # 创建 main.py
    main_py = f'''"""
{name} 工具实现
"""


def {name}_example(input: str) -> str:
    """
    示例函数

    参数:
        input: 输入参数

    返回:
        处理结果
    """
    return f"处理结果: {{input}}"
'''

    with open(tool_dir / "main.py", "w", encoding="utf-8") as f:
        f.write(main_py)

    # 创建 SKILL.md
    skill_md = f"""# {name} 工具

## 概述

{tool_json["description"]}

## 安装

```bash
heimaclaw tool install /path/to/heimaclaw-tool-{name}
```

## 函数

### {name}_example

示例函数

**参数:**
- input (string): 输入参数

**返回:**
- 处理结果字符串

## 使用示例

```python
# 在 Agent 中使用
# 工具会自动加载到 Agent 的工具注册表
```

## 版本历史

### v1.0.0
- 初始版本
"""

    with open(tool_dir / "SKILL.md", "w", encoding="utf-8") as f:
        f.write(skill_md)

    success(f"工具模板创建成功: {tool_dir}")
    info("下一步:")
    info(f"  1. 编辑 {tool_dir}/main.py 实现功能")
    info(f"  2. 编辑 {tool_dir}/tool.json 添加更多函数")
    info(f"  3. 安装: heimaclaw tool install {tool_dir}")


# ==================== monitoring 子命令 ====================

monitoring_app = typer.Typer(help="监控和统计命令")
app.add_typer(monitoring_app, name="monitoring")


@monitoring_app.command("token-stats")
def monitoring_token_stats(
    agent_id: Optional[str] = typer.Option(None, "--agent", "-a", help="过滤 Agent ID"),
    provider: Optional[str] = typer.Option(None, "--provider", "-p", help="过滤提供商"),
    days: int = typer.Option(7, "--days", "-d", help="统计最近多少天"),
) -> None:
    """
    显示 token 使用统计
    """
    from datetime import datetime, timedelta

    from rich.table import Table

    from heimaclaw.monitoring.metrics import get_token_tracker

    tracker = get_token_tracker()

    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    end_date = datetime.now().strftime("%Y-%m-%d")

    stats = tracker.get_stats(
        agent_id=agent_id,
        provider=provider,
        start_date=start_date,
        end_date=end_date,
    )

    # 总体统计
    table = Table(title=f"Token 使用统计（最近 {days} 天）")
    table.add_column("指标")
    table.add_column("值")

    table.add_row("请求次数", str(stats["request_count"]))
    table.add_row("总输入 Token", f"{stats['total_prompt_tokens']:,}")
    table.add_row("总输出 Token", f"{stats['total_completion_tokens']:,}")
    table.add_row("总 Token", f"{stats['total_tokens']:,}")
    table.add_row("平均延迟", f"{stats['avg_latency_ms']}ms")
    table.add_row("最小延迟", f"{stats['min_latency_ms']}ms")
    table.add_row("最大延迟", f"{stats['max_latency_ms']}ms")

    console.print(table)

    # 按提供商统计
    if stats["by_provider"]:
        provider_table = Table(title="按提供商统计")
        provider_table.add_column("提供商")
        provider_table.add_column("请求次数")
        provider_table.add_column("Token 数")

        for item in stats["by_provider"]:
            provider_table.add_row(
                item["provider"],
                str(item["count"]),
                f"{item['tokens']:,}",
            )

        console.print(provider_table)

    # 按模型统计
    if stats["by_model"]:
        model_table = Table(title="按模型统计（Top 10）")
        model_table.add_column("模型")
        model_table.add_column("请求次数")
        model_table.add_column("Token 数")

        for item in stats["by_model"]:
            model_table.add_row(
                item["model"],
                str(item["count"]),
                f"{item['tokens']:,}",
            )

        console.print(model_table)


@monitoring_app.command("daily-usage")
def monitoring_daily_usage(
    agent_id: Optional[str] = typer.Option(None, "--agent", "-a", help="过滤 Agent ID"),
    days: int = typer.Option(7, "--days", "-d", help="查询最近多少天"),
) -> None:
    """
    显示每日使用量
    """
    from rich.table import Table

    from heimaclaw.monitoring.metrics import get_token_tracker

    tracker = get_token_tracker()
    usage = tracker.get_daily_usage(agent_id=agent_id, days=days)

    if not usage:
        info("暂无使用记录")
        return

    table = Table(title=f"每日使用量（最近 {days} 天）")
    table.add_column("日期")
    table.add_column("请求次数")
    table.add_column("Token 数")
    table.add_column("平均延迟")

    for item in usage:
        table.add_row(
            item["date"],
            str(item["request_count"]),
            f"{item['total_tokens']:,}",
            f"{item['avg_latency_ms']}ms",
        )

    console.print(table)


@monitoring_app.command("clear-old")
def monitoring_clear_old(
    days: int = typer.Option(90, "--days", "-d", help="保留最近多少天的数据"),
) -> None:
    """
    清理旧的使用记录
    """
    from heimaclaw.monitoring.metrics import get_token_tracker

    tracker = get_token_tracker()
    deleted = tracker.clear_old_records(days)

    success(f"已清理 {deleted} 条旧记录（保留 {days} 天内数据）")


# ==================== 长连接服务命令 ====================


@app.command("start-ws")
def start_ws_command() -> None:
    """
    启动飞书 WebSocket 长连接服务

    无需配置 Webhook URL，使用飞书官方 SDK 建立长连接。
    """
    import asyncio

    from heimaclaw.feishu_ws_server import main

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        info("服务已停止")


# ==================== Agent 绑定命令 ====================

bindings_app = typer.Typer(help="Agent 绑定管理")
app.add_typer(bindings_app, name="bindings")


@bindings_app.command("bind-user")
def bind_user(
    user_id: str = typer.Argument(..., help="用户 ID"),
    agent: str = typer.Option("default", "--agent", "-a", help="Agent 名称"),
) -> None:
    """绑定用户到 Agent"""
    from heimaclaw.agent.router import AgentRouter

    router = AgentRouter()
    router.bind_user(user_id, agent)

    success(f"已绑定用户 {user_id} 到 Agent {agent}")


@bindings_app.command("bind-group")
def bind_group(
    chat_id: str = typer.Argument(..., help="群聊 ID"),
    agent: str = typer.Option("default", "--agent", "-a", help="Agent 名称"),
) -> None:
    """绑定群聊到 Agent"""
    from heimaclaw.agent.router import AgentRouter

    router = AgentRouter()
    router.bind_group(chat_id, agent)

    success(f"已绑定群聊 {chat_id} 到 Agent {agent}")


@bindings_app.command("unbind-user")
def unbind_user(user_id: str = typer.Argument(..., help="用户 ID")) -> None:
    """解绑用户"""
    from heimaclaw.agent.router import AgentRouter

    router = AgentRouter()
    router.unbind_user(user_id)

    success(f"已解绑用户 {user_id}")


@bindings_app.command("unbind-group")
def unbind_group(chat_id: str = typer.Argument(..., help="群聊 ID")) -> None:
    """解绑群聊"""
    from heimaclaw.agent.router import AgentRouter

    router = AgentRouter()
    router.unbind_group(chat_id)

    success(f"已解绑群聊 {chat_id}")


@bindings_app.command("set-default")
def set_default_agent(
    agent: str = typer.Argument(..., help="Agent 名称"),
) -> None:
    """设置默认 Agent"""
    from heimaclaw.agent.router import AgentRouter

    router = AgentRouter()
    router.set_default(agent)

    success(f"已设置默认 Agent: {agent}")


@bindings_app.command("list")
def list_bindings() -> None:
    """列出所有绑定"""
    from rich.table import Table

    from heimaclaw.agent.router import AgentRouter

    router = AgentRouter()
    bindings = router.get_bindings()

    if not bindings:
        info("暂无绑定")
        return

    table = Table(title="Agent 绑定列表")
    table.add_column("类型")
    table.add_column("ID")
    table.add_column("Agent")

    for key, agent in bindings.items():
        if key == "default":
            table.add_row("默认", "-", agent)
        elif key.startswith("user:"):
            table.add_row("用户", key[5:], agent)
        elif key.startswith("group:"):
            table.add_row("群聊", key[6:], agent)

    console.print(table)


@bindings_app.command("clear")
def clear_bindings(
    confirm: bool = typer.Option(False, "--yes", "-y", help="确认清空"),
) -> None:
    """清空所有绑定"""
    if not confirm:
        warning("使用 --yes 确认清空所有绑定")
        return

    from heimaclaw.agent.router import AgentRouter

    router = AgentRouter()
    router.clear_bindings()

    success("已清空所有绑定")

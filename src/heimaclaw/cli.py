import heimaclaw.paths as paths
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

import os
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
        help=f"项目初始化路径，默认为 {paths.INSTALL_ROOT}",
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

    project_path = Path(path) if path else paths.INSTALL_ROOT

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

    
    # 创建默认 Agent
    init_default_agent(project_path)
    success("  创建默认 Agent: default")
    
    success(f"初始化完成: {project_path}")
    info("下一步: 运行 'heimaclaw config show' 查看配置")



def init_default_agent(project_path: "Path") -> None:
    """创建全局默认的 Agent"""
    import json
    agents_dir = project_path / "data" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    
    default_agent_dir = agents_dir / "default"
    default_agent_dir.mkdir(parents=True, exist_ok=True)
    
    config = {
        "name": "default",
        "description": "系统默认的全局 Agent，支持多模态（需配置 glm-4v 等大模型）",
        "enabled": True,
        "llm": {
            "provider": "zhipu",
            "model_name": "glm-4v",
            "api_key": "de4e3dc9f9d14c75bb2b4a38df59b2b9.CuO0DXKvTfYWVhVu",
            "temperature": 0.7,
            "max_tokens": 8192
        },
        "sandbox": {
            "enabled": False
        }
    }
    
    config_file = default_agent_dir / "agent.json"
    if not config_file.exists():
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)


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

# ==================== install 命令 ====================


@app.command("install")
def install_command(
    force: bool = typer.Option(False, "--force", "-f", help="强制覆盖已存在的配置"),
) -> None:
    """
    自动安装 HeiMaClaw（创建目录、复制模板、初始化配置）
    """
    import shutil
    from pathlib import Path
    
    title("HeiMaClaw 安装向导")
    
    source_dir = Path(__file__).parent.parent.parent
    install_config_dir = paths.CONFIG_DIR
    agents_dir = Path.home() / ".heimaclaw" / "agents"
    
    info("[1/4] 创建目录结构...")
    install_config_dir.mkdir(parents=True, exist_ok=True)
    Path.home() / ".heimaclaw".mkdir(parents=True, exist_ok=True)
    agents_dir.mkdir(parents=True, exist_ok=True)
    success("  目录创建完成")
    
    info("[2/4] 初始化全局配置...")
    config_template = source_dir / "config" / "config.toml.template"
    config_target = install_config_dir / "config.toml"
    if config_target.exists() and not force:
        info("  全局配置已存在 (跳过)")
    else:
        if config_template.exists():
            shutil.copy(config_template, config_target)
        success(f"  全局配置已创建: {config_target}")
    
    info("[3/4] 创建默认 Agent...")
    default_agent_target = agents_dir / "default" / "agent.json"
    if default_agent_target.exists() and not force:
        info("  默认 Agent 已存在 (跳过)")
    else:
        default_agent_target.parent.mkdir(parents=True, exist_ok=True)
        agent_json = '{"name":"default","display_name":"heimaclaw","channel":"feishu","enabled":true,"feishu":{"app_id":"","app_secret":""},"llm":{"provider":"openai","model_name":"glm-5","base_url":"https://open.bigmodel.cn/api/coding/paas/v4","api_key":"","temperature":0.7,"max_tokens":4096},"sandbox":{"enabled":true,"memory_mb":128,"cpu_count":1}}'
        default_agent_target.write_text(agent_json)
        success(f"  默认 Agent 已创建: {default_agent_target}")
    
    info("[4/4] 设置权限...")
    import os
    if config_target.exists():
        os.chmod(config_target, 0o600)
    if default_agent_target.exists():
        os.chmod(default_agent_target, 0o600)
    success("  权限设置完成 (600)")
    
    from rich.panel import Panel
    console.print(Panel(
        "安装完成！\n\n"
        "下一步操作:\n"
        "1. 编辑配置: heimaclaw config edit\n"
        "2. 启动服务: heimaclaw start --feishu --multi-process",
        title="安装成功", style="green"
    ))



# ==================== start 命令 ====================


@app.command("start")
def start_command(
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="监听地址"),
    port: int = typer.Option(8000, "--port", "-p", help="监听端口"),
    workers: int = typer.Option(1, "--workers", "-w", help="工作进程数"),
    reload: bool = typer.Option(False, "--reload", help="开发模式自动重载"),
    feishu: bool = typer.Option(True, "--feishu/--no-feishu", help="启动飞书服务"),
    multi_process: bool = typer.Option(False, "--multi-process/--single-process", help="多进程模式（每个 App 独立进程）"),
    http: bool = typer.Option(True, "--http/--no-http", help="启动 HTTP API 服务"),
    daemon: bool = typer.Option(False, "--daemon", "-d", help="后台守护进程模式运行"),
) -> None:
    """
    启动 HeiMaClaw 服务

    启动 HTTP API 服务和可选的飞书长连接服务。
    默认同时启动 HTTP API (端口 8000) 和飞书长连接。

    示例:
        heimaclaw start                    # 启动全部服务
        heimaclaw start --feishu         # 只启动飞书服务
        heimaclaw start --http           # 只启动 HTTP 服务
        heimaclaw start --reload         # 开发模式（代码自动重载）
        heimaclaw start --daemon         # 后台守护进程模式运行
    """
    import os
    import sys
    import threading
    from pathlib import Path
    
    # PID 文件路径
    run_dir = paths.get_run_dir()
    if not run_dir.exists():
        try:
            run_dir.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            run_dir = Path.home() / ".heimaclaw" / "run"
            run_dir.mkdir(parents=True, exist_ok=True)
            
    pid_file = run_dir / "heimaclaw.pid"
    
    if pid_file.exists():
        try:
            old_pid = int(pid_file.read_text().strip())
            # 检查进程是否存在
            os.kill(old_pid, 0)
            error(f"HeiMaClaw 服务已在运行 (PID: {old_pid})")
            raise typer.Exit(1)
        except (ValueError, OSError):
            # 进程不存在或 PID 文件损坏，清理无效的 PID 文件
            pid_file.unlink()

    if daemon:
        title("启动 HeiMaClaw 服务 (后台模式)")
        import subprocess
        
        # 准备新进程的命令
        cmd = [sys.executable, "-m", "heimaclaw.cli", "start"]
        if host != "0.0.0.0": cmd.extend(["--host", host])
        if port != 8000: cmd.extend(["--port", str(port)])
        if workers != 1: cmd.extend(["--workers", str(workers)])
        if reload: cmd.append("--reload")
        if not feishu: cmd.append("--no-feishu")
        if not http: cmd.append("--no-http")
        
        log_dir = paths.get_log_dir()
        if not log_dir.exists():
            log_dir = Path.home() / ".heimaclaw" / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            
        out_log = open(log_dir / "heimaclaw.out", "a")
        err_log = open(log_dir / "heimaclaw.err", "a")
        
        # 启动子进程
        process = subprocess.Popen(
            cmd,
            stdout=out_log,
            stderr=err_log,
            start_new_session=True  # 脱离当前终端
        )
        
        pid_file.write_text(str(process.pid))
        success(f"HeiMaClaw 服务已在后台启动，PID: {process.pid}")
        info(f"输出日志: {out_log.name}")
        info(f"错误日志: {err_log.name}")
        return

    title("启动 HeiMaClaw 服务")
    
    # 写入当前 PID
    pid_file.write_text(str(os.getpid()))

    info(f"HTTP API: {'启用' if http else '禁用'} (端口 {port})")
    info(f"飞书长连接: {'启用' if feishu else '禁用'}")
    info(f"工作进程: {workers}")

    if reload:
        warning("开发模式已启用，代码变更将自动重载")

    def run_http():
        """启动 HTTP 服务"""
        if not http:
            return
        import uvicorn

        uvicorn.run(
            "heimaclaw.server:app",
            host=host,
            port=port,
            workers=workers if not reload else 1,
            reload=reload,
        )

    def run_feishu():
        """启动飞书长连接服务"""
        if not feishu:
            return
        
        if multi_process:
            # 多进程模式
            info("使用多进程飞书服务架构")
            from heimaclaw.feishu_multiprocess import start_service, stop_service
            import signal
            
            # 写入 PID 文件
            pid_file.write_text(str(os.getpid()))
            
            # 注册信号处理
            def signal_handler(sig, frame):
                info("收到停止信号...")
                if pid_file.exists():
                    pid_file.unlink()
                stop_service()
                sys.exit(0)
            
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
            
            # 启动服务（阻塞）
            service = start_service()
            try:
                while True:
                    import time
                    time.sleep(1)
            except KeyboardInterrupt:
                stop_service()
        else:
            # 单进程模式（原有逻辑）
            import asyncio
            from heimaclaw.feishu_ws_server import main as feishu_main
            asyncio.run(feishu_main())

    try:
        if feishu and http:
            # 同时启动两个服务
            http_thread = threading.Thread(target=run_http, daemon=True)
            http_thread.start()
            run_feishu()
        elif feishu:
            run_feishu()
        else:
            run_http()

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
    from pathlib import Path  # 确保 Path 可用
    import os
    
    title("HeiMaClaw 状态")

    # 读取 PID 文件判断服务状态
    run_dir = paths.get_run_dir()
    pid_file = run_dir / "heimaclaw.pid"
    
    service_status = "[yellow]未启动[/yellow]"
    service_detail = "-"
    sandbox_status = "[yellow]未初始化[/yellow]"
    active_agents = "[dim]0[/dim]"
    active_sessions = "[dim]0[/dim]"
    
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            import os
            if os.path.exists(f"/proc/{pid}"):
                service_status = "[green]运行中[/green]"
                service_detail = f"PID: {pid}"
            else:
                service_status = "[red]已停止[/red]"
                service_detail = "PID 文件过期"
        except Exception:
            service_status = "[red]错误[/red]"
            service_detail = "PID 文件损坏"
    
    # 读取 Agent 列表获取活跃 Agent 数量（检查两个可能的目录）
    agents_count = 0
    agents_dirs = [
        paths.AGENTS_DIR,
        Path.home() / ".heimaclaw" / "agents",
    ]
    for ad in agents_dirs:
        if ad.exists():
            count = sum(1 for d in ad.iterdir() if d.is_dir() and (d / "agent.json").exists())
            if count > agents_count:
                agents_count = count
    
    # 统计活跃会话数量
    sessions_count = 0
    for ad in agents_dirs:
        sessions_dir = ad.parent / "sessions"
        if sessions_dir.exists():
            for session_subdir in sessions_dir.iterdir():
                if session_subdir.is_dir():
                    sessions_count += len(list(session_subdir.glob("*.json")))
    
    # 统计沙箱数量
    sandbox_dir = paths.SANDBOX_DIR
    sandbox_count = 0
    running_sandbox_count = 0
    if sandbox_dir.exists():
        sandbox_count = len([d for d in sandbox_dir.iterdir() if d.is_dir()])
        running_sandbox_count = len([d for d in sandbox_dir.iterdir() if d.is_dir() and (d / "api.sock").exists()])
    
    if agents_count > 0:
        active_agents = f"[green]{agents_count}[/green]"
    else:
        active_agents = "[dim]0[/dim]"
    
    sandbox_detail = f"[dim]{running_sandbox_count} / {sandbox_count}[/dim]" if sandbox_count > 0 else "-"
    sandbox_status = "[green]运行中[/green]" if running_sandbox_count > 0 else "[yellow]未初始化[/yellow]"
    sessions_detail = f"[green]{sessions_count}[/green]" if sessions_count > 0 else "[dim]0[/dim]"
    
    # 服务状态
    table = Table(title="服务状态", show_header=True, header_style="cyan bold")
    table.add_column("项目")
    table.add_column("状态")
    table.add_column("详情")
    # 获取运行中的 Agent 名称
    running_agents = ""
    if service_status == "[green]运行中[/green]":
        agent_names = []
        for ad in agents_dirs:
            if ad.exists():
                for d in ad.iterdir():
                    if d.is_dir() and (d / "agent.json").exists():
                        agent_names.append(d.name)
        running_agents = ", ".join(agent_names) if agent_names else "-"
    
    table.add_row("服务", service_status, service_detail)
    table.add_row("沙箱后端", sandbox_status, sandbox_detail)
    table.add_row("预热池", "[dim]0 / 5[/dim]", "-")
    table.add_row("活跃 Agent", active_agents, running_agents if running_agents else "-")
    table.add_row("活跃会话", sessions_detail, "-")

    console.print(table)

    # 渠道状态 - 读取真实配置
    from pathlib import Path
    import tomli
    
    channel_table = Table(title="渠道状态", show_header=True, header_style="cyan bold")
    channel_table.add_column("渠道")
    channel_table.add_column("状态")
    channel_table.add_column("配置")
    
    # 读取配置
    config_path = paths.CONFIG_FILE
    if not config_path.exists():
        config_path = Path.home() / ".heimaclaw" / "config.toml"
    
    feishu_status = "[yellow]未配置[/yellow]"
    feishu_config = "-"
    
    if config_path.exists():
        try:
            with open(config_path, "rb") as f:
                config = tomli.load(f)
            feishu = config.get("channels", {}).get("feishu", {})
            if feishu.get("app_id"):
                feishu_status = "[green]已配置[/green]"
                feishu_config = feishu.get("app_id", "-")[:15] + "..."
        except Exception:
            pass
    
    channel_table.add_row("飞书", feishu_status, feishu_config)
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
    config_path = paths.CONFIG_FILE
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

    config_path = paths.CONFIG_FILE
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

    config_path = paths.CONFIG_FILE
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

    config_path = paths.CONFIG_FILE
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


@agent_app.command("list")
def agent_list(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="显示详细信息"),
    show_secrets: bool = typer.Option(False, "--show-secrets", help="显示完整 AppSecret (慎用)"),
) -> None:
    """
    列出所有 Agent 及其配置状态
    
    示例:
        heimaclaw agent list              # 简洁列表
        heimaclaw agent list -v           # 详细列表
        heimaclaw agent list --show-secrets  # 显示完整密钥（慎用）
    """
    import json
    import re as re_module
    from pathlib import Path
    from rich.table import Table
    from rich.panel import Panel

    title("Agent 列表")

    # 检查两个可能的 Agent 配置目录
    agents_dirs = [
        paths.AGENTS_DIR,
        Path.home() / ".heimaclaw" / "agents",
    ]

    agents = []
    seen_names = set()  # 避免重复
    agents_detail = {}  # 存储详细信息用于 verbose 模式
    
    for agents_dir in agents_dirs:
        if not agents_dir.exists():
            continue
        for agent_dir in agents_dir.iterdir():
            if not agent_dir.is_dir():
                continue
            config_file = agent_dir / "agent.json"
            if config_file.exists():
                try:
                    with open(config_file, encoding="utf-8") as f:
                        config = json.load(f)
                except:
                    continue
                name = config.get("name", agent_dir.name)
                if name in seen_names:
                    continue
                seen_names.add(name)
                
                # 获取模型信息
                llm_cfg = config.get("llm", {})
                model_name = llm_cfg.get("model_name", "-")
                
                # 获取 display_name
                display = config.get("display_name", name)
                
                # 获取飞书配置
                feishu_cfg = config.get("feishu", {})
                app_id = feishu_cfg.get("app_id", "")
                app_secret = feishu_cfg.get("app_secret", "")
                
                # 掩码处理
                app_id_display = app_id[:10] + "..." if len(app_id) > 10 else (app_id or "❌ 未配置")
                if app_secret:
                    app_secret_display = app_secret[:6] + "***" + app_secret[-4:] if len(app_secret) > 12 else "***"
                else:
                    app_secret_display = "❌ 未配置"
                
                # 验证状态
                app_id_valid = bool(re_module.match(r'^cli_[a-zA-Z0-9]+$', app_id)) if app_id else False
                
                app_id_status = "[green]✅[/green]" if app_id_valid else "[red]❌[/red]"
                
                # 获取沙箱状态
                sandbox_enabled = config.get("sandbox", {}).get("enabled", False)
                sandbox_type = config.get("sandbox", {}).get("type", "docker")
                sandbox_str = f"[green]✅ {sandbox_type}[/green]" if sandbox_enabled else "[dim]❌ 禁用[/dim]"
                
                # 判断 Agent 是否正在运行
                import os
                is_running = False
                run_dir = paths.get_run_dir()
                if run_dir.exists():
                    pid_file = run_dir / "heimaclaw.pid"
                    if pid_file.exists():
                        try:
                            pid = int(pid_file.read_text().strip())
                            if os.path.exists(f"/proc/{pid}"):
                                is_running = True
                        except:
                            pass
                
                status_str = "[green]🟢 运行中[/green]" if is_running else "[yellow]⚠️ 已配置[/yellow]"
                
                # 基本模式
                if not verbose:
                    agents.append([
                        name,
                        display,
                        model_name,
                        app_id_status,
                        status_str,
                    ])
                else:
                    # 详细模式
                    agents_detail[name] = {
                        "name": name,
                        "display": display,
                        "description": config.get("description", "-"),
                        "model_name": model_name,
                        "app_id": app_id,
                        "app_id_display": app_id_display,
                        "app_id_valid": app_id_valid,
                        "app_secret": app_secret if show_secrets else app_secret_display,
                        "app_secret_valid": len(app_secret) >= 16 if app_secret else False,
                        "enabled": config.get("enabled", True),
                        "sandbox_enabled": sandbox_enabled,
                        "sandbox_type": sandbox_type,
                        "is_running": is_running,
                        "config_path": str(config_file),
                    }
    
    if not verbose:
        # 简洁模式
        if agents:
            print_table("Agent 列表", agents, ["名称", "飞书名", "模型", "AppID", "状态"])
        else:
            info("暂无 Agent")
    else:
        # 详细模式
        if not agents_detail:
            info("暂无 Agent")
            return
        
        for name, detail in agents_detail.items():
            status_icon = "[green]🟢[/green]" if detail["is_running"] else "[yellow]⚠️[/yellow]"
            
            # 构建详细面板内容
            content_lines = [
                f"[bold]描述:[/bold] {detail['description']}",
                f"[bold]模型:[/bold] {detail['model_name']}",
                f"",
                f"[bold cyan]飞书配置:[/bold cyan]",
                f"  AppID:     {detail['app_id_display']} {('[green]✅[/green]' if detail['app_id_valid'] else '[red]❌[/red]')}",
                f"  AppSecret: {detail['app_secret']} {('[green]✅[/green]' if detail['app_secret_valid'] else '[red]❌[/red]')}",
                f"",
                f"[bold magenta]沙箱:[/bold magenta]",
                f"  {'✅ 启用' if detail['sandbox_enabled'] else '❌ 禁用'} ({detail['sandbox_type']})",
                f"",
                f"[bold]配置文件:[/bold] {detail['config_path']}",
            ]
            
            panel_content = "\n".join(content_lines)
            panel = Panel(
                panel_content,
                title=f"{status_icon} {name} (显示名: {detail['display']})",
                style="cyan",
            )
            console.print(panel)
            console.print()




@agent_app.command("validate")
def agent_validate(
    agent_name: str = typer.Argument(None, help="指定 Agent 名称（不指定则验证所有）"),
    fix: bool = typer.Option(False, "--fix", "-f", help="自动修复可修复的问题"),
) -> None:
    """
    验证 Agent 配置的完整性和正确性
    
    验证规则:
    - AppID 格式必须为 cli_ 开头
    - AppSecret 长度 >= 16
    - Agent 名称只能包含字母、数字、下划线
    - Display Name 不能为空
    - LLM API Key 不能为空
    - 配置文件必须存在且可读
    
    示例:
        heimaclaw agent validate              # 验证所有 Agent
        heimaclaw agent validate coder_heima  # 验证指定 Agent
        heimaclaw agent validate --fix        # 验证并自动修复
    """
    import json
    import re as re_module
    from pathlib import Path
    from typing import NamedTuple

    class ValidationResult(NamedTuple):
        agent_name: str
        field: str
        status: str  # "✅", "❌", "⚠️"
        message: str

    title("Agent 配置验证")

    # 检查两个可能的 Agent 配置目录
    agents_dirs = [
        paths.AGENTS_DIR,
        Path.home() / ".heimaclaw" / "agents",
    ]

    all_results: list[ValidationResult] = []
    agents_found = set()

    for agents_dir in agents_dirs:
        if not agents_dir.exists():
            continue
        for agent_dir in agents_dir.iterdir():
            if not agent_dir.is_dir():
                continue
                
            agent_name_str = agent_dir.name
            
            # 如果指定了名称，跳过不匹配的
            if agent_name and agent_name_str != agent_name:
                continue
            
            config_file = agent_dir / "agent.json"
            
            # 跳过没有 agent.json 的目录（如 memory、data 等系统目录）
            if not config_file.exists():
                continue
            
            # 读取配置
            try:
                with open(config_file, encoding="utf-8") as f:
                    config = json.load(f)
            except json.JSONDecodeError as e:
                all_results.append(ValidationResult(
                    agent_name_str,
                    "配置文件",
                    "❌",
                    f"JSON 解析失败: {e}"
                ))
                continue
            except Exception as e:
                all_results.append(ValidationResult(
                    agent_name_str,
                    "配置文件",
                    "❌",
                    f"读取失败: {e}"
                ))
                continue
            
            agents_found.add(agent_name_str)
            
            # 1. 验证 Agent 名称
            name_in_config = config.get("name", "")
            if not re_module.match(r'^[a-zA-Z0-9_]{2,32}$', name_in_config):
                all_results.append(ValidationResult(
                    agent_name_str,
                    "Agent 名称",
                    "❌",
                    f"无效的名称: '{name_in_config}' (应为 2-32 位字母、数字、下划线)"
                ))
            else:
                all_results.append(ValidationResult(
                    agent_name_str,
                    "Agent 名称",
                    "✅",
                    f"有效: {name_in_config}"
                ))
            
            # 2. 验证 Display Name
            display_name = config.get("display_name", "")
            if not display_name or len(display_name.strip()) == 0:
                all_results.append(ValidationResult(
                    agent_name_str,
                    "Display Name",
                    "⚠️",
                    "未设置，将使用 Agent 名称"
                ))
            else:
                all_results.append(ValidationResult(
                    agent_name_str,
                    "Display Name",
                    "✅",
                    f"有效: {display_name}"
                ))
            
            # 3. 验证飞书 AppID
            feishu_cfg = config.get("feishu", {})
            app_id = feishu_cfg.get("app_id", "")
            if not app_id:
                all_results.append(ValidationResult(
                    agent_name_str,
                    "AppID",
                    "❌",
                    "未配置飞书 AppID"
                ))
            elif not re_module.match(r'^cli_[a-zA-Z0-9]+$', app_id):
                all_results.append(ValidationResult(
                    agent_name_str,
                    "AppID",
                    "❌",
                    f"格式错误: {app_id} (应以 cli_ 开头)"
                ))
            else:
                all_results.append(ValidationResult(
                    agent_name_str,
                    "AppID",
                    "✅",
                    f"格式正确: {app_id[:15]}..."
                ))
            
            # 4. 验证飞书 AppSecret
            app_secret = feishu_cfg.get("app_secret", "")
            if not app_secret:
                all_results.append(ValidationResult(
                    agent_name_str,
                    "AppSecret",
                    "❌",
                    "未配置飞书 AppSecret"
                ))
            elif len(app_secret) < 16:
                all_results.append(ValidationResult(
                    agent_name_str,
                    "AppSecret",
                    "❌",
                    f"长度不足: {len(app_secret)} < 16"
                ))
            else:
                all_results.append(ValidationResult(
                    agent_name_str,
                    "AppSecret",
                    "✅",
                    f"长度: {len(app_secret)} 位"
                ))
            
            # 5. 验证 LLM API Key
            llm_cfg = config.get("llm", {})
            api_key = llm_cfg.get("api_key", "")
            if not api_key:
                all_results.append(ValidationResult(
                    agent_name_str,
                    "LLM API Key",
                    "❌",
                    "未配置 LLM API Key"
                ))
            elif len(api_key) < 10:
                all_results.append(ValidationResult(
                    agent_name_str,
                    "LLM API Key",
                    "⚠️",
                    f"长度可疑: {len(api_key)} < 10"
                ))
            else:
                all_results.append(ValidationResult(
                    agent_name_str,
                    "LLM API Key",
                    "✅",
                    f"已配置 ({len(api_key)} 位)"
                ))
            
            # 6. 验证 LLM 模型
            model_name = llm_cfg.get("model_name", "")
            if not model_name:
                all_results.append(ValidationResult(
                    agent_name_str,
                    "LLM 模型",
                    "⚠️",
                    "未指定模型"
                ))
            else:
                all_results.append(ValidationResult(
                    agent_name_str,
                    "LLM 模型",
                    "✅",
                    f"使用: {model_name}"
                ))
            
            # 7. 验证 enabled 状态
            enabled = config.get("enabled", True)
            if not enabled:
                all_results.append(ValidationResult(
                    agent_name_str,
                    "启用状态",
                    "⚠️",
                    "Agent 已禁用"
                ))
            else:
                all_results.append(ValidationResult(
                    agent_name_str,
                    "启用状态",
                    "✅",
                    "正常启用"
                ))
            
            # 8. 验证沙箱配置
            sandbox_cfg = config.get("sandbox", {})
            sandbox_enabled = sandbox_cfg.get("enabled", False)
            sandbox_type = sandbox_cfg.get("type", "docker")
            valid_types = ["docker", "firecracker", "process"]
            if sandbox_enabled and sandbox_type not in valid_types:
                all_results.append(ValidationResult(
                    agent_name_str,
                    "沙箱类型",
                    "⚠️",
                    f"未知类型: {sandbox_type}"
                ))
            else:
                all_results.append(ValidationResult(
                    agent_name_str,
                    "沙箱配置",
                    "✅",
                    f"{'启用' if sandbox_enabled else '禁用'} ({sandbox_type})"
                ))

    # 如果指定了名称但没找到
    if agent_name and agent_name not in agents_found:
        error(f"Agent 不存在: {agent_name}")
        # 搜索相似名称
        console.print("\n[dim]可用 Agent:[/dim]")
        for ad in agents_dirs:
            if ad.exists():
                for d in ad.iterdir():
                    if d.is_dir():
                        console.print(f"  - {d.name}")
        raise typer.Exit(1)

    # 输出结果
    if not all_results:
        info("没有找到需要验证的 Agent")
        return

    # 按 Agent 分组显示
    from collections import defaultdict
    by_agent = defaultdict(list)
    for r in all_results:
        by_agent[r.agent_name].append(r)

    for agent_n, results in by_agent.items():
        console.print(f"\n[bold cyan]▸ {agent_n}[/bold cyan]")
        for r in results:
            status_color = "green" if r.status == "✅" else ("red" if r.status == "❌" else "yellow")
            console.print(f"  {r.status} [{status_color}]{r.field}[/{status_color}]: {r.message}")

    # 汇总统计
    total = len(all_results)
    passed = sum(1 for r in all_results if r.status == "✅")
    warnings = sum(1 for r in all_results if r.status == "⚠️")
    failed = sum(1 for r in all_results if r.status == "❌")

    console.print()
    summary = f"总计: [green]✅ {passed}[/green] | [yellow]⚠️ {warnings}[/yellow] | [red]❌ {failed}[/red]"
    console.print(summary)

    if failed > 0:
        console.print("\n[red]❌ 验证失败，请修复上述错误后再启动服务[/red]")
        raise typer.Exit(1)
    elif warnings > 0:
        console.print("\n[yellow]⚠️ 验证通过但有警告，建议检查[/yellow]")
    else:
        console.print("\n[green]✅ 所有检查通过！[/green]")



# ==================== Agent CRUD 命令 ====================


@agent_app.command("add")
def agent_add(
    name: str = typer.Argument(..., help="Agent 名称（字母、数字、下划线）"),
    display_name: str = typer.Option(None, "--display-name", "-d", help="飞书显示名称"),
    description: str = typer.Option("", "--description", help="Agent 描述"),
    app_id: str = typer.Option(..., "--app-id", "-i", help="飞书 AppID (cli_xxx)"),
    app_secret: str = typer.Option(..., "--app-secret", "-s", help="飞书 AppSecret"),
    llm_model: str = typer.Option("glm-5", "--llm-model", "-m", help="LLM 模型"),
    llm_api_key: str = typer.Option("", "--llm-api-key", "-k", help="LLM API Key"),
    sandbox: bool = typer.Option(True, "--sandbox/--no-sandbox", help="启用/禁用沙箱"),
) -> None:
    """
    创建新 Agent（敏感信息自动加密存储）
    
    示例:
        heimaclaw agent create myagent -i cli_xxx -s xxx -k xxx
    """
    from heimaclaw.agent.manager import AgentManager, CreateAgentRequest
    
    title(f"创建 Agent: {name}")
    
    manager = AgentManager()
    
    # 使用名称作为 display_name 如果未指定
    if not display_name:
        display_name = name
    
    # 创建请求
    request = CreateAgentRequest(
        name=name,
        display_name=display_name,
        description=description,
        app_id=app_id,
        app_secret=app_secret,
        llm_model=llm_model,
        llm_api_key=llm_api_key,
        sandbox_enabled=sandbox,
    )
    
    ok, msg, agent_info = manager.create_agent(request)
    
    if ok:
        success(msg)
        info(f"配置文件: {agent_info.config_path}")
    else:
        error(f"创建失败: {msg}")
        raise typer.Exit(1)


@agent_app.command("update")
def agent_update(
    name: str = typer.Argument(..., help="Agent 名称"),
    display_name: str = typer.Option(None, "--display-name", "-d", help="飞书显示名称"),
    description: str = typer.Option(None, "--description", help="Agent 描述"),
    app_id: str = typer.Option(None, "--app-id", "-i", help="飞书 AppID"),
    app_secret: str = typer.Option(None, "--app-secret", "-s", help="飞书 AppSecret（留空不更新）"),
    llm_model: str = typer.Option(None, "--llm-model", "-m", help="LLM 模型"),
    llm_api_key: str = typer.Option(None, "--llm-api-key", "-k", help="LLM API Key"),
    sandbox: bool = typer.Option(None, "--sandbox/--no-sandbox", help="启用/禁用沙箱"),
    enable: bool = typer.Option(None, "--enable/--disable", help="启用/禁用 Agent"),
) -> None:
    """
    更新 Agent 配置（敏感信息自动加密存储）
    
    示例:
        heimaclaw agent update myagent -d "My Bot" -s new_secret
        heimaclaw agent update myagent --disable
    """
    from heimaclaw.agent.manager import AgentManager, UpdateAgentRequest
    
    title(f"更新 Agent: {name}")
    
    manager = AgentManager()
    
    # 构建更新请求
    request = UpdateAgentRequest(
        display_name=display_name,
        description=description,
        app_id=app_id,
        app_secret=app_secret if app_secret else None,  # None = 不更新
        llm_model=llm_model,
        llm_api_key=llm_api_key if llm_api_key else None,
        sandbox_enabled=sandbox,
        enabled=enable,
    )
    
    ok, msg = manager.update_agent(name, request)
    
    if ok:
        success(msg)
    else:
        error(f"更新失败: {msg}")
        raise typer.Exit(1)


@agent_app.command("delete")
def agent_delete(
    name: str = typer.Argument(..., help="Agent 名称"),
    force: bool = typer.Option(False, "--force", "-f", help="跳过确认直接删除"),
) -> None:
    """
    删除 Agent
    
    示例:
        heimaclaw agent delete myagent
        heimaclaw agent delete myagent --force
    """
    from heimaclaw.agent.manager import AgentManager
    
    title(f"删除 Agent: {name}")
    
    manager = AgentManager()
    
    # 确认删除
    if not force:
        warning(f"即将删除 Agent '{name}'，此操作不可恢复！")
        if not typer.confirm("确认删除？"):
            info("已取消")
            return
    
    ok, msg = manager.delete_agent(name)
    
    if ok:
        success(msg)
    else:
        error(f"删除失败: {msg}")
        raise typer.Exit(1)


@agent_app.command("encrypt")
def agent_encrypt(
    name: str = typer.Argument(None, help="Agent 名称（不指定则加密所有）"),
    all: bool = typer.Option(False, "--all", "-a", help="加密所有 Agent"),
) -> None:
    """
    将敏感信息加密存储
    
    示例:
        heimaclaw agent encrypt myagent     # 加密指定 Agent
        heimaclaw agent encrypt --all       # 加密所有 Agent
    """
    from heimaclaw.agent.manager import AgentManager
    
    title("敏感信息加密")
    
    manager = AgentManager()
    
    if all or not name:
        # 加密所有
        success_count, fail_count = manager.encrypt_all()
        console.print(f"\n[bold]加密完成:[/bold]")
        console.print(f"  [green]✅ 成功: {success_count}[/green]")
        console.print(f"  [red]❌ 失败: {fail_count}[/red]")
    else:
        # 加密指定
        ok, msg = manager.encrypt_existing(name)
        if ok:
            success(msg)
        else:
            error(f"加密失败: {msg}")
            raise typer.Exit(1)



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
            (
                tool.description[:30] + "..."
                if len(tool.description) > 30
                else tool.description
            ),
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


# ==================== 会话管理命令 ====================


@app.command("session", hidden=True)
def session_command() -> None:
    """会话管理命令组"""
    info("使用以下子命令：")
    info("  heimaclaw session list          - 列出所有会话")
    info("  heimaclaw session clear <id>    - 清除指定会话")
    info("  heimaclaw session clear-all     - 清除所有会话")


@app.command("session-list", hidden=True)
def session_list() -> None:
    """列出所有会话"""
    from pathlib import Path

    from rich.table import Table

    sessions_dir = Path("/tmp/heimaclaw/sessions")

    if not sessions_dir.exists():
        info("暂无会话记录")
        return

    table = Table(title="会话列表")
    table.add_column("Agent")
    table.add_column("会话文件")

    for agent_dir in sessions_dir.iterdir():
        if agent_dir.is_dir():
            for session_file in agent_dir.glob("*.json"):
                table.add_row(agent_dir.name, session_file.name)

    console.print(table)


@app.command("session-clear", hidden=True)
def session_clear(
    agent: str = typer.Option(..., "--agent", "-a", help="Agent 名称"),
) -> None:
    """清除指定 Agent 的所有会话"""
    import shutil
    from pathlib import Path

    sessions_dir = Path(f"/tmp/heimaclaw/sessions/{agent}")

    if sessions_dir.exists():
        shutil.rmtree(sessions_dir)
        success(f"已清除 Agent {agent} 的所有会话")
    else:
        info(f"Agent {agent} 暂无会话记录")


@app.command("session-clear-all", hidden=True)
def session_clear_all(
    confirm: bool = typer.Option(False, "--yes", "-y", help="确认清除"),
) -> None:
    """清除所有会话"""
    import shutil
    from pathlib import Path

    if not confirm:
        warning("使用 --yes 确认清除所有会话")
        return

    sessions_dir = Path("/tmp/heimaclaw/sessions")

    if sessions_dir.exists():
        shutil.rmtree(sessions_dir)
        success("已清除所有会话")
    else:
        info("暂无会话记录")


# ==================== 编译命令 ====================



@agent_app.command("clear-history")
def agent_clear_history(
    name: str = typer.Argument(..., help="Agent 名称"),
) -> None:
    """清除指定 Agent 的历史会话"""
    import shutil
    from pathlib import Path

    sessions_dir = Path(f"/tmp/heimaclaw/sessions/{name}")
    if sessions_dir.exists():
        shutil.rmtree(sessions_dir)
        success(f"已清除 Agent {name} 的所有会话历史")
    else:
        info(f"Agent {name} 暂无会话记录")

@agent_app.command("compile", hidden=True)
def agent_compile(
    agent_name: Optional[str] = typer.Argument(
        None, help="Agent 名称（不指定则编译所有）"
    ),
    force: bool = typer.Option(False, "--force", "-f", help="强制重新编译"),
    watch: bool = typer.Option(False, "--watch", "-w", help="监听模式（自动编译）"),
) -> None:
    """
    编译 Agent 配置

    将 Markdown 配置编译为高性能的 JSON 配置。

    示例:
        heimaclaw agent compile              # 编译所有 agent
        heimaclaw agent compile my-agent     # 编译指定 agent
        heimaclaw agent compile --force      # 强制重新编译
        heimaclaw agent compile --watch      # 监听模式
    """
    import asyncio
    from pathlib import Path

    from heimaclaw.config.compiler import ConfigCompiler

    # 获取 agents 目录
    agents_dir = paths.AGENTS_DIR
    if not agents_dir.exists():
        agents_dir = Path.home() / ".heimaclaw" / "agents"

    if not agents_dir.exists():
        error("Agents 目录不存在，请先运行 'heimaclaw init' 初始化")
        raise typer.Exit(1)

    compiler = ConfigCompiler(agents_dir)

    if watch:
        # 监听模式
        title("监听模式")
        info("监听配置文件变化...")
        info("按 Ctrl+C 退出")

        async def watch_and_compile():
            import asyncio

            try:
                while True:
                    # 初始编译
                    if agent_name:
                        await compiler.compile_agent(agent_name, force=True)
                    else:
                        results = await compiler.compile_all(force=force)
                        success_count = sum(1 for v in results.values() if v)
                        total_count = len(results)
                        info(f"编译完成: {success_count}/{total_count}")

                    # 每 5 秒检查一次
                    await asyncio.sleep(5)
            except KeyboardInterrupt:
                info("停止监听")

        try:
            asyncio.run(watch_and_compile())
        except KeyboardInterrupt:
            pass
    else:
        # 单次编译
        if agent_name:
            # 编译单个 agent
            success_flag = asyncio.run(compiler.compile_agent(agent_name, force))
            if not success_flag:
                raise typer.Exit(1)
        else:
            # 编译所有 agent
            title("编译所有 Agent")
            results = asyncio.run(compiler.compile_all(force))

            # 显示结果
            success_count = sum(1 for v in results.values() if v)
            total_count = len(results)

            if total_count == 0:
                warning("没有找到需要编译的 Agent")
                return

            # 打印结果表格
            table = Table(title=f"编译结果 ({success_count}/{total_count})")
            table.add_column("Agent", style="cyan")
            table.add_column("状态", style="magenta")

            for name, result in results.items():
                status = "✅ 成功" if result else "❌ 失败"
                table.add_row(name, status)

            console.print(table)

            if success_count < total_count:
                raise typer.Exit(1)


@agent_app.command("set-llm")
def agent_set_llm(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Agent 名称"),
    provider: str = typer.Option("openai", "--provider", "-p", help="模型提供商 (openai, zhipu, qwen, kimi, deepseek等)"),
    model: str = typer.Option(..., "--model", "-m", help="模型名称"),
    api_key: str = typer.Option(..., "--api-key", "-k", help="API Key（必填）"),
    base_url: Optional[str] = typer.Option(None, "--base-url", "-b", help="自定义 Base URL"),
) -> None:
    """
    设置 Agent 的 LLM 模型配置
    
    示例:
        heimaclaw agent set-llm default -m glm-5 -k xxx -b https://open.bigmodel.cn/api/coding/paas/v4
        heimaclaw agent set-llm coder_heima -m glm-4 -k xxx -p openai -b https://open.bigmodel.cn/api/coding/paas/v4
    """
    import json
    from pathlib import Path

    agents_dir = paths.AGENTS_DIR
    if not agents_dir.exists():
        agents_dir = Path.home() / ".heimaclaw" / "agents"

    config_file = agents_dir / name / "agent.json"

    if not config_file.exists():
        error(f"Agent 不存在: {name}")
        raise typer.Exit(1)

    with open(config_file, encoding="utf-8") as f:
        config = json.load(f)

    # 预设厂商配置
    preset_urls = {
        "openai": "https://api.openai.com/v1",
        "zhipu": "https://open.bigmodel.cn/api/paas/v4",
        "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "kimi": "https://api.moonshot.cn/v1",
        "deepseek": "https://api.deepseek.com/v1",
        "bigmodel": "https://open.bigmodel.cn/api/coding/paas/v4",
    }

    # 如果没有提供 base_url，使用预设或提示错误
    if not base_url:
        base_url = preset_urls.get(provider.lower(), "")
    
    if not base_url:
        error(f"未知的 provider '{provider}'，请通过 --base-url 指定 API 地址")
        raise typer.Exit(1)

    if not api_key or api_key == "xxx":
        error("API Key 不能为空，请通过 --api-key 指定")
        raise typer.Exit(1)

    config["llm"] = {
        "provider": provider,
        "model_name": model,
        "api_key": api_key,
        "base_url": base_url,
        "temperature": 0.7,
        "max_tokens": 8192,
    }

    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    success(f"已更新 Agent {name} 的 LLM 配置")
    info(f"  提供商: {provider}")
    info(f"  模型: {model}")
    info(f"  Base URL: {base_url}")

@agent_app.command("set-vision")
def agent_set_vision(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Agent 名称"),
    enabled: bool = typer.Option(False, "--enable/--disable", help="是否启用视觉理解"),
    model: str = typer.Option(None, "--model", "-m", help="视觉模型名称 (如 glm-4v)"),
    api_key: str = typer.Option(None, "--api-key", "-k", help="API Key（与 LLM 相同可省略）"),
    base_url: Optional[str] = typer.Option(None, "--base-url", "-b", help="自定义 Base URL"),
) -> None:
    """
    设置 Agent 的视觉理解配置（可选，覆盖全局配置）
    
    示例:
        heimaclaw agent set-vision default --enable -m glm-4v -k xxx
        heimaclaw agent set-vision coder_heima --disable
    """
    import json
    from pathlib import Path

    agents_dir = paths.AGENTS_DIR
    if not agents_dir.exists():
        agents_dir = Path.home() / ".heimaclaw" / "agents"

    config_file = agents_dir / name / "agent.json"

    if not config_file.exists():
        error(f"Agent 不存在: {name}")
        raise typer.Exit(1)

    with open(config_file, encoding="utf-8") as f:
        config = json.load(f)

    # 读取 LLM 的 api_key 作为默认值
    llm_api_key = api_key or config.get("llm", {}).get("api_key", "")
    
    vision_config = {
        "enabled": enabled,
        "model": model or "glm-4v",
        "api_key": llm_api_key,
        "base_url": base_url or config.get("llm", {}).get("base_url", "https://open.bigmodel.cn/api/coding/paas/v4"),
    }
    
    config["vision"] = vision_config

    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    status = "已启用" if enabled else "已禁用"
    success(f"已更新 Agent {name} 的视觉配置: {status}")
    if enabled:
        info(f"  模型: {vision_config['model']}")
        info(f"  Base URL: {vision_config['base_url']}")


@agent_app.command("set-policy")
def agent_set_policy(
    name: str = typer.Argument(..., help="Agent 名称"),
    mode: str = typer.Option(
        "mention", "--mode", "-m", help="响应模式: mention/open/disabled"
    ),
    scope: str = typer.Option(
        "both", "--scope", "-s", help="作用范围: private/group/both"
    ),
    allow_users: bool = typer.Option(
        True, "--allow-users/--no-allow-users", help="是否允许所有用户"
    ),
    allow_groups: bool = typer.Option(
        True, "--allow-groups/--no-allow-groups", help="是否允许所有群"
    ),
) -> None:
    """
    设置 Agent 的响应策略

    示例:
        # 群聊只响应 @，私聊正常响应
        heimaclaw agent set-policy my-agent --mode mention --scope both

        # 只允许私聊
        heimaclaw agent set-policy my-agent --mode open --scope private

        # 禁用群聊
        heimaclaw agent set-policy my-agent --scope private
    """
    import json
    from pathlib import Path

    # 验证参数
    if mode not in ("mention", "open", "disabled"):
        error(f"无效的响应模式: {mode}")
        raise typer.Exit(1)

    if scope not in ("private", "group", "both"):
        error(f"无效的作用范围: {scope}")
        raise typer.Exit(1)

    # 查找 Agent 配置
    agents_dir = paths.AGENTS_DIR
    if not agents_dir.exists():
        agents_dir = Path.home() / ".heimaclaw" / "agents"

    config_file = agents_dir / name / "agent.json"

    if not config_file.exists():
        error(f"Agent 不存在: {name}")
        raise typer.Exit(1)

    # 读取配置
    with open(config_file, encoding="utf-8") as f:
        config = json.load(f)

    # 更新策略
    config["policy"] = {
        "mode": mode,
        "scope": scope,
        "allow_all_users": allow_users,
        "allow_all_groups": allow_groups,
        "whitelist_users": config.get("policy", {}).get("whitelist_users", []),
        "whitelist_groups": config.get("policy", {}).get("whitelist_groups", []),
    }

    # 保存配置
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    success(f"已更新 Agent {name} 的策略")
    info(f"  响应模式: {mode}")
    info(f"  作用范围: {scope}")
    info(f"  允许所有用户: {allow_users}")
    info(f"  允许所有群: {allow_groups}")


@agent_app.command("show-policy")
def agent_show_policy(
    name: str = typer.Argument(..., help="Agent 名称"),
) -> None:
    """
    显示 Agent 的响应策略
    """
    import json
    from pathlib import Path

    from rich.table import Table

    # 查找 Agent 配置
    agents_dir = paths.AGENTS_DIR
    if not agents_dir.exists():
        agents_dir = Path.home() / ".heimaclaw" / "agents"

    config_file = agents_dir / name / "agent.json"

    if not config_file.exists():
        error(f"Agent 不存在: {name}")
        raise typer.Exit(1)

    # 读取配置
    with open(config_file, encoding="utf-8") as f:
        config = json.load(f)

    policy = config.get("policy", {})

    # 显示策略
    table = Table(title=f"Agent {name} 响应策略")
    table.add_column("配置项")
    table.add_column("值")
    table.add_column("说明")

    mode = policy.get("mode", "mention")
    mode_desc = {"mention": "@提及才响应", "open": "响应所有人", "disabled": "禁用"}
    table.add_row("响应模式", mode, mode_desc.get(mode, ""))

    scope = policy.get("scope", "both")
    scope_desc = {"private": "只私聊", "group": "只群聊", "both": "私聊+群聊"}
    table.add_row("作用范围", scope, scope_desc.get(scope, ""))

    allow_users = policy.get("allow_all_users", True)
    table.add_row("允许所有用户", str(allow_users), "")

    allow_groups = policy.get("allow_all_groups", True)
    table.add_row("允许所有群", str(allow_groups), "")

    whitelist_users = policy.get("whitelist_users", [])
    table.add_row(
        "用户白名单",
        str(len(whitelist_users)),
        ", ".join(whitelist_users) if whitelist_users else "-",
    )

    whitelist_groups = policy.get("whitelist_groups", [])
    table.add_row(
        "群白名单",
        str(len(whitelist_groups)),
        ", ".join(whitelist_groups) if whitelist_groups else "-",
    )

    console.print(table)


# ==================== 服务生命周期命令 ====================


@app.command("stop")
def stop_command(
    force: bool = typer.Option(False, "--force", "-f", help="强制终止"),
) -> None:
    """
    停止 HeiMaClaw 服务

    示例:
        heimaclaw stop        # 正常停止
        heimaclaw stop -f    # 强制终止
    """
    import os
    import signal
    from pathlib import Path

    title("停止 HeiMaClaw 服务")

    run_dir = paths.get_run_dir()
    if not run_dir.exists():
        run_dir = Path.home() / ".heimaclaw" / "run"
        
    pid_file = run_dir / "heimaclaw.pid"
    
    if not pid_file.exists():
        info("未找到 PID 文件，服务可能未在运行")
        return
        
    try:
        pid = int(pid_file.read_text().strip())
    except ValueError:
        error("PID 文件格式错误")
        pid_file.unlink()
        return

    try:
        if force:
            os.kill(pid, signal.SIGKILL)
        else:
            os.kill(pid, signal.SIGTERM)
        success(f"已发送停止信号给进程 (PID: {pid})")
        pid_file.unlink(missing_ok=True)
    except ProcessLookupError:
        warning(f"进程 {pid} 不存在，清理失效的 PID 文件")
        pid_file.unlink()
    except PermissionError:
        error(f"没有权限停止进程 {pid}，请使用 root 权限运行")
        raise typer.Exit(1)


@app.command("restart")
def restart_command(
    force: bool = typer.Option(False, "--force", "-f", help="强制终止"),
) -> None:
    """
    重启 HeiMaClaw 服务

    示例:
        heimaclaw restart      # 正常重启
        heimaclaw restart -f   # 强制重启
    """
    import os
    import signal
    import subprocess
    import sys
    from pathlib import Path

    title("重启 HeiMaClaw 服务")

    run_dir = paths.get_run_dir()
    if not run_dir.exists():
        run_dir = Path.home() / ".heimaclaw" / "run"
        
    pid_file = run_dir / "heimaclaw.pid"
    
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            if force:
                os.kill(pid, signal.SIGKILL)
            else:
                os.kill(pid, signal.SIGTERM)
            info(f"已停止旧服务 (PID: {pid})")
            pid_file.unlink(missing_ok=True)
            
            # 等待进程结束
            import time
            for _ in range(50):
                try:
                    os.kill(pid, 0)
                    time.sleep(0.1)
                except ProcessLookupError:
                    break
        except (ValueError, ProcessLookupError):
            warning("清理失效的 PID 文件")
            pid_file.unlink(missing_ok=True)
        except PermissionError:
            error(f"没有权限停止进程 {pid}，请使用 root 权限运行")
            raise typer.Exit(1)

    info("启动新服务...")
    # 继承当前进程的环境变量启动新服务 (使用 daemon 模式)
    cmd = [sys.executable, "-m", "heimaclaw.cli", "start", "--daemon"]
    try:
        subprocess.run(cmd, check=True)
        success("服务已重启!")
    except subprocess.CalledProcessError:
        error("启动新服务失败")
        raise typer.Exit(1)


@app.command("pid")
def pid_command() -> None:
    """
    查看 HeiMaClaw 服务进程 ID

    示例:
        heimaclaw pid
    """
    import subprocess

    result = subprocess.run(
        ["pgrep", "-f", "heimaclaw"],
        capture_output=True,
        text=True,
    )
    pids = result.stdout.strip().split("\n")

    if not pids or not pids[0]:
        info("没有运行中的 HeiMaClaw 服务")
        return

    console.print("\n[bold]运行中的 HeiMaClaw 进程:[/bold]")
    for pid in pids:
        if pid.isdigit():
            console.print(f"  PID: {pid}")


@app.command("log")
def log_command(
    lines: int = typer.Option(50, "--lines", "-n", help="显示最近 N 行日志"),
    follow: bool = typer.Option(False, "--follow", "-f", help="实时跟踪日志"),
) -> None:
    """
    查看 HeiMaClaw 服务日志

    示例:
        heimaclaw log              # 查看最近 50 行
        heimaclaw log -n 100      # 查看最近 100 行
        heimaclaw log -f          # 实时跟踪日志
    """
    import subprocess

    # 查找日志文件
    log_paths = [
        Path("/tmp/heimaclaw.log"),
        Path.home() / ".heimaclaw" / "logs" / "heimaclaw.log",
        paths.get_log_dir() / "heimaclaw.log",
    ]

    log_file = None
    for path in log_paths:
        if path.exists():
            log_file = path
            break

    if not log_file:
        info("未找到日志文件")
        info("日志可能写入 stdout/stderr，请使用 'heimaclaw log -f' 实时查看")
        return

    title(f"HeiMaClaw 日志: {log_file}")

    if follow:
        # 实时跟踪
        subprocess.run(["tail", "-n", str(lines), "-f", str(log_file)])
    else:
        # 显示最近 N 行
        result = subprocess.run(
            ["tail", "-n", str(lines), str(log_file)],
            capture_output=True,
            text=True,
        )
        if result.stdout:
            console.print(result.stdout)
        if result.stderr:
            error(result.stderr)



@app.command("task-status")
def task_status(
    session_key: Optional[str] = typer.Option(None, "--session", "-s", help="过滤特定会话的任务"),
    all: bool = typer.Option(False, "--all", "-a", help="显示所有任务（包括已完成/失败的）"),
) -> None:
    """
    查看当前子任务(Subagent)的执行状态
    """
    from heimaclaw.core.subagent_registry import SubagentRegistry
    from heimaclaw.core.subagent_state import SubagentStatus
    from rich.table import Table
    from pathlib import Path

    registry_dir = Path(".openclaw/subagent-state")
    if not registry_dir.exists():
        info("暂无任务记录")
        return

    registry = SubagentRegistry(state_dir=str(registry_dir))
    
    if session_key:
        runs = registry.list_for_requester(session_key)
    elif not all:
        runs = registry.list_active()
    else:
        runs = list(registry._runs.values())

    if not runs:
        info("暂无符合条件的任务")
        return

    table = Table(title="Subagent 任务状态", show_header=True, header_style="cyan bold")
    table.add_column("Run ID", style="dim")
    table.add_column("状态")
    table.add_column("模型")
    table.add_column("任务描述")
    table.add_column("会话 ID")

    for run in sorted(runs, key=lambda x: x.created_at, reverse=True)[:50]:
        status_color = "green" if run.status == SubagentStatus.COMPLETED else (
            "yellow" if run.status in (SubagentStatus.RUNNING, SubagentStatus.PENDING) else "red"
        )
        table.add_row(
            run.run_id[:8] + "...",
            f"[{status_color}]{run.status.value}[/{status_color}]",
            run.model or "默认",
            (run.task[:30] + "...") if len(run.task) > 30 else run.task,
            run.requester_id[:10] + "..." if len(run.requester_id) > 10 else run.requester_id
        )

    console.print(table)


if __name__ == "__main__":
    app()

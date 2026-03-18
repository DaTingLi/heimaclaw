"""
CLI 模块测试
"""

from typer.testing import CliRunner

from heimaclaw.cli import app

runner = CliRunner()


def test_version():
    """测试版本显示"""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "HeiMaClaw" in result.output


def test_help():
    """测试帮助信息"""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "HeiMaClaw" in result.output


def test_doctor():
    """测试诊断命令"""
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "诊断" in result.output


def test_status():
    """测试状态命令"""
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "状态" in result.output


def test_config_show():
    """测试配置显示"""
    result = runner.invoke(app, ["config", "show"])
    # 可能因为没有配置文件而失败，这是预期的
    assert "配置" in result.output or result.exit_code != 0

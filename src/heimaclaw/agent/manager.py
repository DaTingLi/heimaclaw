"""
Agent 配置管理器

提供 Agent 的 CRUD 操作、配置验证、敏感信息加密存储。
"""

import fcntl
import json
import os
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from pydantic import BaseModel

import heimaclaw.paths as paths
from heimaclaw.console import warning


# ==================== 枚举和模型 ====================


class ValidationStatus(str, Enum):
    PASS = "✅"
    FAIL = "❌"
    WARN = "⚠️"


class ValidationResult(BaseModel):
    """验证结果"""
    field: str
    status: ValidationStatus
    message: str


class AgentInfo(BaseModel):
    """Agent 信息"""
    name: str
    display_name: str
    description: str = ""
    channel: str = "feishu"
    enabled: bool = True
    app_id: str = ""
    app_secret_encrypted: str = ""  # 加密后的存储
    llm_provider: str = "openai"
    llm_model: str = ""
    llm_api_key_encrypted: str = ""
    sandbox_enabled: bool = True
    sandbox_type: str = "docker"
    config_path: str = ""


class CreateAgentRequest(BaseModel):
    """创建 Agent 请求"""
    name: str
    display_name: str
    description: str = ""
    app_id: str
    app_secret: str
    llm_model: str = "glm-5"
    llm_api_key: str = ""
    sandbox_enabled: bool = True


class UpdateAgentRequest(BaseModel):
    """更新 Agent 请求"""
    display_name: Optional[str] = None
    description: Optional[str] = None
    app_id: Optional[str] = None
    app_secret: Optional[str] = None  # None 表示不更新
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    llm_api_key: Optional[str] = None
    sandbox_enabled: Optional[bool] = None
    sandbox_type: Optional[str] = None
    enabled: Optional[bool] = None


# ==================== 加密引擎（模块级单例，进程安全） ====================

_encryption_lock_file: Optional[Path] = None
_encryption_key: Optional[bytes] = None


def _get_encryption_key() -> bytes:
    """
    获取加密密钥（进程安全，单例模式）
    
    使用文件锁确保多进程环境下密钥生成/读取的原子性。
    """
    global _encryption_key
    
    if _encryption_key is not None:
        return _encryption_key
    
    key_file = Path.home() / ".heimaclaw" / ".key"
    lock_file = Path.home() / ".heimaclaw" / ".key.lock"
    
    key_file.parent.mkdir(parents=True, exist_ok=True)
    
    # 使用文件锁确保原子性
    with open(lock_file, 'w') as lf:
        fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
        try:
            if key_file.exists():
                with open(key_file, 'rb') as f:
                    _encryption_key = f.read()
            else:
                _encryption_key = Fernet.generate_key()
                with open(key_file, 'wb') as f:
                    f.write(_encryption_key)
                os.chmod(key_file, 0o600)
        finally:
            fcntl.flock(lf.fileno(), fcntl.LOCK_UN)
    
    return _encryption_key


def _get_fernet() -> Fernet:
    """获取 Fernet 加密实例"""
    return Fernet(_get_encryption_key())


# ==================== 解密错误（自定义异常） ====================


class DecryptionError(Exception):
    """解密失败异常"""
    pass


# ==================== AgentManager 类 ====================


class AgentManager:
    """
    Agent 配置管理器
    
    功能：
    - 配置验证（AppID、AppSecret 格式）
    - CRUD 操作（创建、读取、更新、删除）
    - 敏感信息加密存储
    """

    def __init__(self, agents_dir: Optional[Path] = None):
        """
        初始化 AgentManager
        
        Args:
            agents_dir: Agent 配置目录，默认为 ~/.heimaclaw/agents
        """
        # 支持多个 agents 目录
        self._agents_dirs = []
        if agents_dir:
            self._agents_dirs = [agents_dir]
        else:
            self._agents_dirs = paths.get_agents_dirs()
            # 确保 ~/.heimaclaw/agents 也在列表中
            legacy = Path.home() / ".heimaclaw" / "agents"
            if legacy not in self._agents_dirs:
                self._agents_dirs.append(legacy)
    
    def _iter_all_agents_dirs(self):
        """迭代所有 agents 目录"""
        for d in self._agents_dirs:
            if d.exists():
                yield d
    
    # ==================== 加密/解密（使用模块级加密引擎） ====================
    
    def _encrypt(self, value: str) -> str:
        """加密字符串"""
        if not value:
            return ""
        return _get_fernet().encrypt(value.encode()).decode()
    
    def _decrypt(self, encrypted: str) -> str:
        """
        解密字符串
        
        Raises:
            DecryptionError: 解密失败时抛出（而非静默返回空字符串）
        """
        if not encrypted:
            return ""
        try:
            return _get_fernet().decrypt(encrypted.encode()).decode()
        except (InvalidToken, ValueError) as e:
            raise DecryptionError(f"解密失败: {e}") from e
        except Exception as e:
            raise DecryptionError(f"未知解密错误: {e}") from e

    # ==================== 验证方法 ====================
    
    @staticmethod
    def validate_app_id(app_id: str) -> ValidationResult:
        """验证 AppID 格式"""
        if not app_id:
            return ValidationResult(
                field="AppID",
                status=ValidationStatus.FAIL,
                message="AppID 不能为空"
            )
        if not re.match(r'^cli_[a-zA-Z0-9]+$', app_id):
            return ValidationResult(
                field="AppID",
                status=ValidationStatus.FAIL,
                message=f"格式错误: {app_id} (应以 cli_ 开头)"
            )
        return ValidationResult(
            field="AppID",
            status=ValidationStatus.PASS,
            message=f"格式正确: {app_id[:15]}..."
        )
    
    @staticmethod
    def validate_app_secret(app_secret: str) -> ValidationResult:
        """验证 AppSecret 格式"""
        if not app_secret:
            return ValidationResult(
                field="AppSecret",
                status=ValidationStatus.FAIL,
                message="AppSecret 不能为空"
            )
        if len(app_secret) < 16:
            return ValidationResult(
                field="AppSecret",
                status=ValidationStatus.FAIL,
                message=f"长度不足: {len(app_secret)} < 16"
            )
        return ValidationResult(
            field="AppSecret",
            status=ValidationStatus.PASS,
            message=f"长度: {len(app_secret)} 位"
        )
    
    @staticmethod
    def validate_agent_name(name: str) -> ValidationResult:
        """验证 Agent 名称"""
        if not name:
            return ValidationResult(
                field="Agent Name",
                status=ValidationStatus.FAIL,
                message="Agent 名称不能为空"
            )
        if not re.match(r'^[a-zA-Z0-9_]{2,32}$', name):
            return ValidationResult(
                field="Agent Name",
                status=ValidationStatus.FAIL,
                message="名称只能包含字母、数字、下划线，2-32位"
            )
        return ValidationResult(
            field="Agent Name",
            status=ValidationStatus.PASS,
            message=f"有效: {name}"
        )
    
    def validate_all(self, name: str) -> list[ValidationResult]:
        """验证指定 Agent 的所有配置"""
        results = []
        
        # 验证名称
        name_result = self.validate_agent_name(name)
        if name_result.status != ValidationStatus.PASS:
            results.append(name_result)
            return results  # 名称无效，后续验证无意义
        
        results.append(name_result)
        
        # 读取配置
        config = self._read_config(name)
        if not config:
            results.append(ValidationResult(
                field="配置文件",
                status=ValidationStatus.FAIL,
                message="配置文件不存在"
            ))
            return results
        
        # 验证 Display Name
        display_name = config.get("display_name", "")
        if not display_name:
            results.append(ValidationResult(
                field="Display Name",
                status=ValidationStatus.WARN,
                message="未设置"
            ))
        else:
            results.append(ValidationResult(
                field="Display Name",
                status=ValidationStatus.PASS,
                message=f"有效: {display_name}"
            ))
        
        # 验证飞书配置
        feishu_cfg = config.get("feishu", {})
        app_id = feishu_cfg.get("app_id", "")
        results.append(self.validate_app_id(app_id))
        
        app_secret = feishu_cfg.get("app_secret", "")
        if not app_secret:
            results.append(ValidationResult(
                field="AppSecret",
                status=ValidationStatus.FAIL,
                message="未配置"
            ))
        elif app_secret.startswith("ENC:"):
            # 已加密，尝试解密后验证
            try:
                decrypted = self._decrypt(app_secret[4:])
                results.append(self.validate_app_secret(decrypted))
            except DecryptionError as e:
                results.append(ValidationResult(
                    field="AppSecret",
                    status=ValidationStatus.FAIL,
                    message=f"解密失败: {e}"
                ))
        else:
            # 未加密
            results.append(self.validate_app_secret(app_secret))
        
        # 验证 LLM 配置
        llm_cfg = config.get("llm", {})
        api_key = llm_cfg.get("api_key", "")
        if api_key:
            if api_key.startswith("ENC:"):
                try:
                    decrypted_key = self._decrypt(api_key[4:])
                    results.append(ValidationResult(
                        field="LLM API Key",
                        status=ValidationStatus.PASS,
                        message=f"已加密存储 ({len(decrypted_key)} 位)"
                    ))
                except DecryptionError as e:
                    results.append(ValidationResult(
                        field="LLM API Key",
                        status=ValidationStatus.FAIL,
                        message=f"解密失败: {e}"
                    ))
            else:
                results.append(ValidationResult(
                    field="LLM API Key",
                    status=ValidationStatus.WARN,
                    message="未加密存储"
                ))
        else:
            results.append(ValidationResult(
                field="LLM API Key",
                status=ValidationStatus.FAIL,
                message="未配置"
            ))
        
        model_name = llm_cfg.get("model_name", "")
        if model_name:
            results.append(ValidationResult(
                field="LLM 模型",
                status=ValidationStatus.PASS,
                message=f"使用: {model_name}"
            ))
        else:
            results.append(ValidationResult(
                field="LLM 模型",
                status=ValidationStatus.WARN,
                message="未指定"
            ))
        
        # 验证沙箱配置
        sandbox_cfg = config.get("sandbox", {})
        sandbox_enabled = sandbox_cfg.get("enabled", False)
        sandbox_type = sandbox_cfg.get("type", "docker")
        valid_types = ["docker", "firecracker", "process"]
        
        if sandbox_enabled and sandbox_type not in valid_types:
            results.append(ValidationResult(
                field="沙箱配置",
                status=ValidationStatus.WARN,
                message=f"未知类型: {sandbox_type}"
            ))
        else:
            results.append(ValidationResult(
                field="沙箱配置",
                status=ValidationStatus.PASS,
                message=f"{'启用' if sandbox_enabled else '禁用'} ({sandbox_type})"
            ))
        
        return results
    
    # ==================== CRUD 操作 ====================
    
    def _read_config(self, name: str) -> Optional[dict]:
        """读取 Agent 配置（搜索所有目录）"""
        for agents_dir in self._iter_all_agents_dirs():
            config_file = agents_dir / name / "agent.json"
            if config_file.exists():
                try:
                    with open(config_file, 'r', encoding='utf-8') as f:
                        return json.load(f)
                except json.JSONDecodeError as e:
                    warning(f"Agent {name} JSON 解析失败: {e}")
                    return None
                except Exception as e:
                    warning(f"读取 Agent {name} 配置失败: {e}")
                    return None
        return None
    
    def _write_config(self, name: str, config: dict) -> bool:
        """写入 Agent 配置（优先使用 ~/.heimaclaw/agents）"""
        target_dir = Path.home() / ".heimaclaw" / "agents" / name
        config_file = target_dir / "agent.json"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        
        # 写入前备份
        if config_file.exists():
            backup_file = config_file.with_suffix('.json.bak')
            try:
                import shutil
                shutil.copy2(config_file, backup_file)
            except Exception as e:
                warning(f"备份配置文件失败: {e}")
        
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            warning(f"写入配置文件失败: {e}")
            return False
    
    def list_agents(self) -> list[AgentInfo]:
        """列出所有 Agent"""
        agents = []
        seen_names = set()  # 避免重复
        
        for agents_dir in self._iter_all_agents_dirs():
            if not agents_dir.exists():
                continue
            for agent_dir in agents_dir.iterdir():
                if not agent_dir.is_dir():
                    continue
                
                config_file = agent_dir / "agent.json"
                if not config_file.exists():
                    continue
                
                config = self._read_config(agent_dir.name)
                if not config:
                    continue
                
                name = config.get("name", agent_dir.name)
                if name in seen_names:
                    continue
                seen_names.add(name)
                
                feishu_cfg = config.get("feishu", {})
                llm_cfg = config.get("llm", {})
                sandbox_cfg = config.get("sandbox", {})
                
                agents.append(AgentInfo(
                    name=name,
                    display_name=config.get("display_name", name),
                    description=config.get("description", ""),
                    channel=config.get("channel", "feishu"),
                    enabled=config.get("enabled", True),
                    app_id=feishu_cfg.get("app_id", ""),
                    app_secret_encrypted=feishu_cfg.get("app_secret", ""),
                    llm_provider=llm_cfg.get("provider", "openai"),
                    llm_model=llm_cfg.get("model_name", ""),
                    llm_api_key_encrypted=llm_cfg.get("api_key", ""),
                    sandbox_enabled=sandbox_cfg.get("enabled", True),
                    sandbox_type=sandbox_cfg.get("type", "docker"),
                    config_path=str(config_file),
                ))
        
        return agents
    
    def get_agent(self, name: str) -> Optional[AgentInfo]:
        """获取指定 Agent"""
        for agent in self.list_agents():
            if agent.name == name:
                return agent
        return None
    
    def create_agent(self, request: CreateAgentRequest) -> tuple[bool, str, Optional[AgentInfo]]:
        """创建新 Agent"""
        # 验证名称
        name_result = self.validate_agent_name(request.name)
        if name_result.status != ValidationStatus.PASS:
            return False, name_result.message, None
        
        # 检查是否已存在
        target_dir = Path.home() / ".heimaclaw" / "agents" / request.name
        if target_dir.exists():
            return False, f"Agent '{request.name}' 已存在", None
        
        # 验证 AppID
        app_id_result = self.validate_app_id(request.app_id)
        if app_id_result.status != ValidationStatus.PASS:
            return False, app_id_result.message, None
        
        # 验证 AppSecret
        app_secret_result = self.validate_app_secret(request.app_secret)
        if app_secret_result.status != ValidationStatus.PASS:
            return False, app_secret_result.message, None
        
        # 检查 AppID 是否已被其他 Agent 使用
        for agent in self.list_agents():
            if agent.app_id == request.app_id:
                return False, f"AppID '{request.app_id[:15]}...' 已被 Agent '{agent.name}' 使用", None
        
        # 构建配置（敏感信息加密存储）
        config = {
            "name": request.name,
            "description": request.description,
            "display_name": request.display_name,
            "channel": "feishu",
            "enabled": True,
            "feishu": {
                "app_id": request.app_id,
                "app_secret": f"ENC:{self._encrypt(request.app_secret)}",
            },
            "llm": {
                "provider": "openai",
                "model_name": request.llm_model,
                "base_url": "https://open.bigmodel.cn/api/coding/paas/v4",
                "api_key": f"ENC:{self._encrypt(request.llm_api_key)}" if request.llm_api_key else "",
                "temperature": 0.7,
                "max_tokens": 4096,
            },
            "sandbox": {
                "enabled": request.sandbox_enabled,
                "type": "docker",
                "memory_mb": 128,
                "cpu_count": 1,
            },
        }
        
        if not self._write_config(request.name, config):
            return False, "写入配置文件失败", None
        
        agent_info = AgentInfo(
            name=request.name,
            display_name=request.display_name,
            description=request.description,
            app_id=request.app_id,
            sandbox_enabled=request.sandbox_enabled,
            llm_model=request.llm_model,
            config_path=str(target_dir / "agent.json"),
        )
        
        return True, f"Agent '{request.name}' 创建成功", agent_info
    
    def update_agent(self, name: str, request: UpdateAgentRequest) -> tuple[bool, str]:
        """更新 Agent 配置"""
        config = self._read_config(name)
        if not config:
            return False, f"Agent '{name}' 不存在"
        
        if request.display_name is not None:
            config["display_name"] = request.display_name
        
        if request.description is not None:
            config["description"] = request.description
        
        if request.enabled is not None:
            config["enabled"] = request.enabled
        
        # 飞书配置更新
        feishu_cfg = config.get("feishu", {})
        if request.app_id is not None:
            app_id_result = self.validate_app_id(request.app_id)
            if app_id_result.status != ValidationStatus.PASS:
                return False, app_id_result.message
            feishu_cfg["app_id"] = request.app_id
        
        if request.app_secret is not None:
            app_secret_result = self.validate_app_secret(request.app_secret)
            if app_secret_result.status != ValidationStatus.PASS:
                return False, app_secret_result.message
            feishu_cfg["app_secret"] = f"ENC:{self._encrypt(request.app_secret)}"
        
        config["feishu"] = feishu_cfg
        
        # LLM 配置更新
        llm_cfg = config.get("llm", {})
        if request.llm_provider is not None:
            llm_cfg["provider"] = request.llm_provider
        if request.llm_model is not None:
            llm_cfg["model_name"] = request.llm_model
        if request.llm_api_key is not None:
            llm_cfg["api_key"] = f"ENC:{self._encrypt(request.llm_api_key)}"
        config["llm"] = llm_cfg
        
        # 沙箱配置更新
        sandbox_cfg = config.get("sandbox", {})
        if request.sandbox_enabled is not None:
            sandbox_cfg["enabled"] = request.sandbox_enabled
        if request.sandbox_type is not None:
            sandbox_cfg["type"] = request.sandbox_type
        config["sandbox"] = sandbox_cfg
        
        if not self._write_config(name, config):
            return False, "写入配置文件失败"
        
        return True, f"Agent '{name}' 更新成功"
    
    def delete_agent(self, name: str) -> tuple[bool, str]:
        """删除 Agent"""
        config = self._read_config(name)
        if not config:
            return False, f"Agent '{name}' 不存在"
        
        agent_dir = None
        for agents_dir in self._iter_all_agents_dirs():
            d = agents_dir / name
            if d.exists():
                agent_dir = d
                break
        
        if not agent_dir:
            return False, f"Agent '{name}' 目录不存在"
        
        try:
            import shutil
            shutil.rmtree(agent_dir)
            return True, f"Agent '{name}' 已删除"
        except Exception as e:
            return False, f"删除失败: {e}"
    
    def encrypt_existing(self, name: str) -> tuple[bool, str]:
        """将现有 Agent 的敏感信息加密存储"""
        config = self._read_config(name)
        if not config:
            return False, f"Agent '{name}' 不存在"
        
        modified = False
        errors = []
        
        # 加密 AppSecret
        feishu_cfg = config.get("feishu", {})
        app_secret = feishu_cfg.get("app_secret", "")
        if app_secret and not app_secret.startswith("ENC:"):
            try:
                feishu_cfg["app_secret"] = f"ENC:{self._encrypt(app_secret)}"
                modified = True
            except Exception as e:
                errors.append(f"AppSecret: {e}")
        
        # 加密 LLM API Key
        llm_cfg = config.get("llm", {})
        api_key = llm_cfg.get("api_key", "")
        if api_key and not api_key.startswith("ENC:"):
            try:
                llm_cfg["api_key"] = f"ENC:{self._encrypt(api_key)}"
                modified = True
            except Exception as e:
                errors.append(f"LLM API Key: {e}")
        
        if errors:
            return False, f"加密失败: {', '.join(errors)}"
        
        if not modified:
            return True, f"Agent '{name}' 无需加密（已加密或无敏感信息）"
        
        config["feishu"] = feishu_cfg
        config["llm"] = llm_cfg
        if not self._write_config(name, config):
            return False, "写入配置文件失败"
        return True, f"Agent '{name}' 敏感信息已加密"
    
    def encrypt_all(self) -> tuple[int, int]:
        """加密所有 Agent 的敏感信息"""
        success = 0
        fail = 0
        for agent in self.list_agents():
            ok, _ = self.encrypt_existing(agent.name)
            if ok:
                success += 1
            else:
                fail += 1
        return success, fail


# 全局实例（不推荐使用，每次都应创建新实例以保证进程隔离）
_manager: Optional[AgentManager] = None


def get_agent_manager() -> AgentManager:
    """获取全局 AgentManager 实例"""
    global _manager
    if _manager is None:
        _manager = AgentManager()
    return _manager

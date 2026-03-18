# 模块接口契约标准 v1.0

## 原则
- 高内聚、低耦合、单一职责
- 所有模块必须定义明确的接口（Pydantic + Protocol）
- 接口变更必须走版本控制（v1 → v2）

## 接口定义规范
每个模块必须在 src/<package>/<module>/interfaces.py 中定义：

from typing import Protocol
from pydantic import BaseModel

class SomeInterface(Protocol):
    def execute(self, input: InputModel) -> OutputModel:
        ...

class InputModel(BaseModel):
    field1: str
    field2: int

class OutputModel(BaseModel):
    result: str
    status: str

## 常用核心接口（全局复用建议）

- CommandRegistry：CLI 命令注册
- ConfigProvider：配置加载与校验
- BackendAdapter：后端抽象（数据库、沙箱、渠道等）
- Runner：核心执行循环
- Store：状态持久化

版本：v1.0
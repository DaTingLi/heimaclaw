#!/usr/bin/env python3
"""
测试 LLMResponse 对象提取修复
"""

from dataclasses import dataclass, field
from typing import Optional, Any

@dataclass
class MockLLMResponse:
    """模拟的 LLMResponse"""
    content: str
    model: str
    provider: str = "test"
    prompt_tokens: int = 100
    completion_tokens: int = 50
    total_tokens: int = 150
    tool_calls: list = field(default_factory=list)
    raw_response: Optional[dict] = None
    finish_reason: str = "stop"
    latency_ms: int = 1000

def extract_content(response: Any) -> str:
    """提取响应内容（修复后的逻辑）"""
    if hasattr(response, 'content'):
        return response.content
    elif not isinstance(response, str):
        return str(response)
    return response

# 测试用例
test_cases = [
    {
        "name": "LLMResponse 对象",
        "input": MockLLMResponse(
            content="你好！我是 ChatGLM，一个人工智能助手。",
            model="glm-4-flash"
        ),
        "expected": "你好！我是 ChatGLM，一个人工智能助手。"
    },
    {
        "name": "普通字符串",
        "input": "这是一个普通字符串响应",
        "expected": "这是一个普通字符串响应"
    },
    {
        "name": "字典对象",
        "input": {"content": "字典内容"},
        "expected": "{'content': '字典内容'}"
    }
]

print("="*60)
print("LLMResponse 对象提取修复测试")
print("="*60)

all_passed = True

for i, test in enumerate(test_cases, 1):
    result = extract_content(test["input"])
    passed = result == test["expected"]
    all_passed = all_passed and passed
    
    status = "✅" if passed else "❌"
    print(f"\n测试 {i}: {test['name']}")
    print(f"{status} 输入类型: {type(test['input'])}")
    print(f"{status} 输出: {result[:50]}...")
    print(f"{status} 预期: {test['expected'][:50]}...")
    print(f"{status} 结果: {'通过' if passed else '失败'}")

print("\n" + "="*60)
if all_passed:
    print("✅ 所有测试通过！修复成功！")
else:
    print("❌ 部分测试失败，请检查")
print("="*60)

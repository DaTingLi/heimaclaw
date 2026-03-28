#!/usr/bin/env python3
"""
飞书文档创建脚本 V2
自动将 HeimaClaw 架构文档写入飞书在线文档
"""

import httpx
import json
import os
import re
from pathlib import Path

# 飞书配置 (从 heimaclaw config.toml 读取)
FEISHU_APP_ID = "cli_a9301fec40395bde"
FEISHU_APP_SECRET = "EWPY3k4fjiMpL5iJx6PFFhEzhLsMMkXd"

# API 端点
FEISHU_BASE_URL = "https://open.feishu.cn/open-apis"


class FeishuDocCreator:
    def __init__(self, app_id: str, app_secret: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self.access_token = None
        self.client = httpx.Client(timeout=60.0)
    
    def get_access_token(self) -> str:
        """获取飞书 access_token"""
        url = f"{FEISHU_BASE_URL}/auth/v3/tenant_access_token/internal"
        
        payload = {
            "app_id": self.app_id,
            "app_secret": self.app_secret
        }
        
        response = self.client.post(url, json=payload)
        result = response.json()
        
        if result.get("code") != 0:
            raise Exception(f"获取 access_token 失败: {result}")
        
        self.access_token = result["tenant_access_token"]
        print(f"✅ 获取 access_token 成功")
        return self.access_token
    
    def create_document(self, title: str) -> str:
        """创建飞书文档"""
        url = f"{FEISHU_BASE_URL}/docx/v1/documents"
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "title": title,
            "folder_token": ""  # 空表示创建在根目录
        }
        
        response = self.client.post(url, headers=headers, json=payload)
        result = response.json()
        
        if result.get("code") != 0:
            raise Exception(f"创建文档失败: {result}")
        
        doc_id = result["data"]["document"]["document_id"]
        print(f"✅ 创建文档成功: {doc_id}")
        return doc_id
    
    def add_text_content(self, document_id: str, content: str):
        """添加文本内容到文档"""
        url = f"{FEISHU_BASE_URL}/docx/v1/documents/{document_id}/blocks/{document_id}/children"
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        # 解析 Markdown 内容
        blocks = self._parse_markdown_to_blocks(content)
        
        # 飞书 API 限制每次最多创建 50 个块
        batch_size = 50
        for i in range(0, len(blocks), batch_size):
            batch = blocks[i:i + batch_size]
            
            payload = {
                "children": batch,
                "index": -1  # 追加到末尾
            }
            
            response = self.client.post(url, headers=headers, json=payload)
            result = response.json()
            
            if result.get("code") != 0:
                print(f"⚠️ 批量添加块失败 (batch {i//batch_size + 1}): {result.get('msg', result)}")
            else:
                print(f"✅ 添加内容块 {i+1}-{min(i+batch_size, len(blocks))}/{len(blocks)}")
    
    def _parse_markdown_to_blocks(self, markdown: str) -> list:
        """将 Markdown 转换为飞书文档块"""
        blocks = []
        lines = markdown.split('\n')
        current_code = []
        in_code_block = False
        code_language = ""
        
        for line in lines:
            # 代码块处理
            if line.startswith('```'):
                if in_code_block:
                    # 结束代码块
                    blocks.append({
                        "block_type": 23,
                        "code": {
                            "style": 1,
                            "elements": [{"text_run": {"content": '\n'.join(current_code)}}]
                        }
                    })
                    current_code = []
                    in_code_block = False
                else:
                    # 开始代码块
                    in_code_block = True
                    code_language = line[3:].strip()
                continue
            
            if in_code_block:
                current_code.append(line)
                continue
            
            # 空行
            if not line.strip():
                continue
            
            # 一级标题
            if line.startswith('# ') and not line.startswith('## '):
                blocks.append({
                    "block_type": 4,
                    "heading1": {
                        "elements": [{"text_run": {"content": line[2:].strip()}}]
                    }
                })
            # 二级标题
            elif line.startswith('## ') and not line.startswith('### '):
                blocks.append({
                    "block_type": 5,
                    "heading2": {
                        "elements": [{"text_run": {"content": line[3:].strip()}}]
                    }
                })
            # 三级标题
            elif line.startswith('### ') and not line.startswith('#### '):
                blocks.append({
                    "block_type": 6,
                    "heading3": {
                        "elements": [{"text_run": {"content": line[4:].strip()}}]
                    }
                })
            # 四级标题
            elif line.startswith('#### '):
                blocks.append({
                    "block_type": 7,
                    "heading4": {
                        "elements": [{"text_run": {"content": line[5:].strip()}}]
                    }
                })
            # 分隔线
            elif line.strip() == '---':
                blocks.append({
                    "block_type": 8
                })
            # 引用
            elif line.startswith('> '):
                blocks.append({
                    "block_type": 12,
                    "quote": {
                        "elements": [{"text_run": {"content": line[2:].strip()}}]
                    }
                })
            # 列表项
            elif line.startswith('- ') or line.startswith('* '):
                blocks.append({
                    "block_type": 13,
                    "bullet": {
                        "elements": [{"text_run": {"content": self._clean_markdown(line[2:].strip())}}]
                    }
                })
            # 有序列表
            elif re.match(r'^\d+\.\s', line):
                content = re.sub(r'^\d+\.\s', '', line)
                blocks.append({
                    "block_type": 14,
                    "ordered": {
                        "elements": [{"text_run": {"content": self._clean_markdown(content)}}]
                    }
                })
            # 表格行 (简化处理)
            elif line.startswith('|'):
                # 飞书表格 API 较复杂，这里简化为文本
                blocks.append({
                    "block_type": 2,
                    "text": {
                        "elements": [{"text_run": {"content": self._clean_markdown(line)}}]
                    }
                })
            # 普通文本
            else:
                cleaned_line = self._clean_markdown(line)
                if cleaned_line.strip():
                    blocks.append({
                        "block_type": 2,
                        "text": {
                            "elements": [{"text_run": {"content": cleaned_line}}]
                        }
                    })
        
        return blocks
    
    def _clean_markdown(self, text: str) -> str:
        """清理 Markdown 格式"""
        # 移除粗体
        text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
        # 移除斜体
        text = re.sub(r'\*([^*]+)\*', r'\1', text)
        # 移除链接，保留文本
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
        # 移除行内代码
        text = re.sub(r'`([^`]+)`', r'\1', text)
        return text
    
    def get_document_url(self, document_id: str) -> str:
        """获取文档 URL"""
        return f"https://feishu.cn/docx/{document_id}"
    
    def close(self):
        """关闭客户端"""
        self.client.close()


def main():
    """主函数"""
    print("=" * 60)
    print("  HeimaClaw 架构文档 → 飞书在线文档")
    print("=" * 60)
    
    # 读取架构文档
    doc_path = Path("/root/heimaclaw_workspace/docs/HeimaClaw_Architecture_Full.md")
    
    if not doc_path.exists():
        print(f"❌ 文档文件不存在: {doc_path}")
        return
    
    with open(doc_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    print(f"📄 读取文档: {doc_path}")
    print(f"📏 文档大小: {len(content)} 字符")
    
    # 创建飞书文档
    creator = FeishuDocCreator(FEISHU_APP_ID, FEISHU_APP_SECRET)
    
    try:
        # 1. 获取 access_token
        creator.get_access_token()
        
        # 2. 创建文档
        doc_id = creator.create_document("HeimaClaw 系统架构文档")
        
        # 3. 添加内容
        print("📝 正在写入文档内容...")
        creator.add_text_content(doc_id, content)
        
        # 4. 获取文档 URL
        doc_url = creator.get_document_url(doc_id)
        
        print("=" * 60)
        print("✅ 飞书文档创建成功！")
        print("=" * 60)
        print(f"📎 文档 URL: {doc_url}")
        print("=" * 60)
        
        # 保存 URL 到文件
        url_file = Path("/root/heimaclaw_workspace/feishu_doc_url.txt")
        with open(url_file, 'w') as f:
            f.write(doc_url)
        print(f"💾 URL 已保存到: {url_file}")
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        creator.close()


if __name__ == "__main__":
    main()

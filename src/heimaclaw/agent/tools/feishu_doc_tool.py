"""
飞书文档创建工具

允许 Agent 创建飞书在线文档、表格、多维表格。
"""
import json
from typing import Any

import lark_oapi as lark
from lark_oapi.api.docx.v1 import Document as DocxDocument
from lark_oapi.api.docx.v1.model.create_document_request import CreateDocumentRequest
from lark_oapi.api.docx.v1.model.create_document_request_body import CreateDocumentRequestBody
from lark_oapi.api.sheets.v3 import Spreadsheet
from lark_oapi.api.sheets.v3.model.create_spreadsheet_request import CreateSpreadsheetRequest
from lark_oapi.api.sheets.v3.model.spreadsheet import Spreadsheet as SpreadsheetModel
from lark_oapi.api.bitable.v1 import App as BitableApp
from lark_oapi.api.bitable.v1.model.create_app_request import CreateAppRequest
from lark_oapi.api.bitable.v1.model.req_app import ReqApp


# ============================================================
# 工具定义（供 Agent 注册使用）
# ============================================================

FEISHU_DOC_TOOL_DEFINITION = {
    "name": "create_feishu_doc",
    "description": "创建飞书在线文档或表格",
    "parameters": {
        "type": "object",
        "properties": {
            "type": {
                "type": "string",
                "description": "文档类型：doc(飞书文档)、sheet(飞书表格)、bitable(多维表格)",
                "enum": ["doc", "sheet", "bitable"]
            },
            "title": {
                "type": "string",
                "description": "文档标题"
            },
            "folder_token": {
                "type": "string",
                "description": "文件夹 token（可选，不填则创建在根目录）",
                "default": ""
            }
        },
        "required": ["type", "title"]
    }
}


# ============================================================
# 全局凭证（由 Worker 在启动时设置）
# ============================================================

_current_app_id: str = ""
_current_app_secret: str = ""


def set_feishu_credentials(app_id: str, app_secret: str) -> None:
    """设置当前 Agent 的飞书凭证（由 Worker 调用）"""
    global _current_app_id, _current_app_secret
    _current_app_id = app_id
    _current_app_secret = app_secret


def _get_client() -> lark.Client:
    """获取飞书 API Client"""
    if not _current_app_id or not _current_app_secret:
        raise ValueError("飞书凭证未设置，请先调用 set_feishu_credentials()")
    return lark.Client(_current_app_id, _current_app_secret)


# ============================================================
# 工具执行函数
# ============================================================

async def feishu_doc_handler(
    type: str,
    title: str,
    folder_token: str = ""
) -> str:
    """
    创建飞书在线文档/表格/多维表格
    
    Args:
        type: 文档类型 - doc/sheet/bitable
        title: 文档标题
        folder_token: 文件夹 token（可选）
    
    Returns:
        JSON 格式的结果，包含 document_id 和 url
    """
    try:
        client = _get_client()
        
        if type == "doc":
            return await _create_document(client, title, folder_token)
        elif type == "sheet":
            return await _create_spreadsheet(client, title, folder_token)
        elif type == "bitable":
            return await _create_bitable(client, title, folder_token)
        else:
            return json.dumps({
                "success": False,
                "error": f"不支持的类型: {type}，支持: doc, sheet, bitable"
            })
            
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"创建飞书文档失败: {str(e)}"
        })


async def _create_document(client: lark.Client, title: str, folder_token: str) -> str:
    """创建飞书文档"""
    try:
        request = (
            CreateDocumentRequest.builder()
            .request_body(
                CreateDocumentRequestBody.builder()
                .title(title)
                .folder_token(folder_token or None)
                .build()
            )
            .build()
        )
        
        response = DocxDocument(client).create(request)
        
        if response.code() != 0:
            return json.dumps({
                "success": False,
                "error": f"创建文档失败: {response.msg()}",
                "code": response.code()
            })
        
        data = response.data
        return json.dumps({
            "success": True,
            "document_id": data.document.document_id,
            "url": data.document.url,
            "title": title,
            "type": "doc"
        }, ensure_ascii=False)
        
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"创建文档异常: {str(e)}"
        })


async def _create_spreadsheet(client: lark.Client, title: str, folder_token: str) -> str:
    """创建飞书表格"""
    try:
        request = (
            CreateSpreadsheetRequest.builder()
            .request_body(
                SpreadsheetModel.builder()
                .title(title)
                .folder_token(folder_token or None)
                .build()
            )
            .build()
        )
        
        response = Spreadsheet(client).create(request)
        
        if response.code() != 0:
            return json.dumps({
                "success": False,
                "error": f"创建表格失败: {response.msg()}",
                "code": response.code()
            })
        
        data = response.data
        return json.dumps({
            "success": True,
            "spreadsheet_id": data.spreadsheet.spreadsheet_id,
            "url": data.spreadsheet.url,
            "title": title,
            "type": "sheet"
        }, ensure_ascii=False)
        
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"创建表格异常: {str(e)}"
        })


async def _create_bitable(client: lark.Client, title: str, folder_token: str) -> str:
    """创建多维表格"""
    try:
        request = (
            CreateAppRequest.builder()
            .request_body(
                ReqApp.builder()
                .name(title)
                .folder_token(folder_token or None)
                .build()
            )
            .build()
        )
        
        response = BitableApp(client).create(request)
        
        if response.code() != 0:
            return json.dumps({
                "success": False,
                "error": f"创建多维表格失败: {response.msg()}",
                "code": response.code()
            })
        
        data = response.data
        return json.dumps({
            "success": True,
            "bitable_id": data.app.app_token,
            "url": data.app.url,
            "title": title,
            "type": "bitable"
        }, ensure_ascii=False)
        
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"创建多维表格异常: {str(e)}"
        })

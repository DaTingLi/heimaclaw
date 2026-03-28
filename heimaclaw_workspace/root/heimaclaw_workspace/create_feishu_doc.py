#!/usr/bin/env python3
"""
创建飞书文档脚本
"""
import os
import sys

# 设置飞书凭证（需要从环境变量获取）
APP_ID = os.getenv("FEISHU_APP_ID", "")
APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")

if not APP_ID or not APP_SECRET:
    print("❌ 错误：请设置飞书凭证环境变量")
    print("   export FEISHU_APP_ID='your_app_id'")
    print("   export FEISHU_APP_SECRET='your_app_secret'")
    sys.exit(1)

try:
    import lark_oapi as lark
    from lark_oapi.api.docx.v1 import Document as DocxDocument
    from lark_oapi.api.docx.v1.model.create_document_request import CreateDocumentRequest
    from lark_oapi.api.docx.v1.model.create_document_request_body import CreateDocumentRequestBody
    
    # 读取文档内容
    doc_path = "/root/heimaclaw_workspace/docs/HeimaClaw_真实架构文档.md"
    with open(doc_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    print(f"📄 文档内容已读取: {len(content)} 字符")
    
    # 创建飞书 Client
    client = lark.Client(APP_ID, APP_SECRET)
    
    # 创建文档请求
    request = (
        CreateDocumentRequest.builder()
        .request_body(
            CreateDocumentRequestBody.builder()
            .title("HeiMaClaw 系统架构文档")
            .folder_token("")  # 根目录
            .build()
        )
        .build()
    )
    
    print("🚀 正在创建飞书文档...")
    
    # 发送请求
    response = DocxDocument(client).create(request)
    
    if response.code() == 0:
        data = response.data
        print("✅ 飞书文档创建成功！")
        print(f"   文档 ID: {data.document.document_id}")
        print(f"   文档 URL: {data.document.url}")
        
        # 保存 URL 到文件
        with open("/root/heimaclaw_workspace/feishu_doc_url.txt", "w") as f:
            f.write(f"文档 ID: {data.document.document_id}\n")
            f.write(f"URL: {data.document.url}\n")
        
        print("\n📝 下一步：")
        print(f"   1. 访问 {data.document.url}")
        print("   2. 手动将 Markdown 内容复制粘贴到文档中")
        print(f"   3. 或使用飞书 API 导入内容（需要额外开发）")
    else:
        print(f"❌ 创建失败: {response.msg()}")
        print(f"   错误码: {response.code()}")
        
except ImportError as e:
    print(f"❌ 缺少依赖: {e}")
    print("   安装: pip install lark-oapi")
except Exception as e:
    print(f"❌ 异常: {e}")
    import traceback
    traceback.print_exc()

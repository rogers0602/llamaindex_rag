"""
此模块定义了用于检索文件内容的API端点。

Author: Guo Lijian
"""
from dependencies import get_db, get_current_user
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from models import DocumentRecord, User
import os


router = APIRouter(prefix="/api/files", tags=["file"])

# 4. 获取文件内容接口 (用于预览)
@router.get("/{filename}")
async def get_file_content(
        filename: str,
        doc_workspace_id: str,
        current_user: User = Depends(get_current_user),  # 鉴权
        db: Session = Depends(get_db)
):
    # 1. 简单鉴权：查询数据库确认用户有权访问该文件所属的 workspace
    doc_record = (db.query(DocumentRecord)
                   .filter(DocumentRecord.filename == filename,
                           DocumentRecord.workspace_id == doc_workspace_id).first())
    if not doc_record:
        raise HTTPException(404, "文件记录不存在")

    # 2. 定位文件路径 .files/{workspace_id}/filename
    file_path = os.path.join("files", doc_workspace_id, filename)
    if not os.path.exists(file_path):
        raise HTTPException(404, "文件未找到")

    # 3. 判断PDF文件类型并返回
    if filename.lower().endswith(".pdf"):
        return FileResponse(
            file_path,
            media_type="application/pdf",
            filename=filename  # 让浏览器知道文件名
        )

    # 如果是文本文件，读取内容返回 JSON (方便前端渲染 + 高亮)
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        return {"type": "text", "content": content}
    except UnicodeDecodeError:
        # 二进制文件(Docx等)需要特殊处理，暂时先当下载处理
        return FileResponse(file_path, filename=filename)


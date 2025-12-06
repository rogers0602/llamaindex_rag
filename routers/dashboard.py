"""
此模块定义了仪表盘的API接口。

它提供有关文档、聊天会话和用户的数据统计信息。

Author: Guo Lijian
"""
import datetime

from fastapi import APIRouter
from dependencies import get_db, get_current_user
from sqlalchemy.orm import Session
from models import DocumentRecord, ChatSession, User, Workspace
from fastapi import Depends

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

# --- 仪表盘统计接口 ---
@router.get("/stats")
async def get_dashboard_stats(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    # 1. 基础查询条件构建
    # 如果是 Admin，看全局；如果是 Member，只看自己部门 + 公共
    global chart_dates, chart_values
    doc_query = db.query(DocumentRecord)
    chat_query = db.query(ChatSession)

    if current_user.role != "admin":
        doc_query = doc_query.filter(
            (DocumentRecord.workspace_id == current_user.department_id) |
            (DocumentRecord.is_global == True)
        )
        # 聊天记录通常只看自己的
        chat_query = chat_query.filter(ChatSession.user_id == current_user.id)

    # 2. 核心指标统计
    total_docs = doc_query.count()
    total_chats = chat_query.count()

    # 统计总存储 (近似值，单位 MB)
    # 注意：file_size 字段之前存的是字符串 "1.2 MB"，这里简单处理，实际建议数据库存 bytes 整数
    # 这里我们只统计数量作为演示，如果你的 file_size 是 int 最好

    # 3. 图表数据：按日期统计最近 7 天的文件上传量
    # PostgreSQL 使用 func.date_trunc 或 cast
    # 简单起见，这里返回最近 5 个上传的文件作为“动态”
    recent_docs = doc_query.order_by(DocumentRecord.upload_date.desc()).limit(5).all()

    recent_docs_data = []
    for d in recent_docs:
        uploader = db.query(User).filter(User.id == d.uploader_id).first()
        recent_docs_data.append({
            "id": str(d.id),
            "name": d.filename,
            "date": d.upload_date.strftime("%Y-%m-%d"),
            "uploader": uploader.username if uploader else "Unknown"
        })

    # 4. 图表数据：文件类型分布 (PDF vs Word vs TXT)
    # 这是一个简单的内存统计，数据量大时建议用 SQL Group By
    all_docs = doc_query.all()
    type_stats = {"PDF": 0, "Word": 0, "Text": 0, "Other": 0}

    for d in all_docs:
        ext = d.filename.split('.')[-1].lower()
        if ext == 'pdf':
            type_stats["PDF"] += 1
        elif ext in ['doc', 'docx']:
            type_stats["Word"] += 1
        elif ext in ['txt', 'md']:
            type_stats["Text"] += 1
        else:
            type_stats["Other"] += 1

        # 真实活跃度统计
        # 1. 确定时间范围 (最近7天)
        today = datetime.datetime.utcnow().date()
        seven_days_ago = today - datetime.timedelta(days=6)

        # 2. 查询最近7天的所有会话记录
        # 注意：这里复用了上面的 chat_query (已经过滤了权限)
        recent_sessions = chat_query.filter(
            ChatSession.created_at >= seven_days_ago
        ).all()

        # 3. 在内存中统计每天的数量
        # 格式: {"12-01": 5, "12-02": 0, ...}
        daily_counts = {}
        for session in recent_sessions:
            # 转成 "MM-DD" 格式字符串
            day_str = session.created_at.strftime("%m-%d")
            daily_counts[day_str] = daily_counts.get(day_str, 0) + 1

        # 4. 生成连续的日期列表 (X轴) 和 对应数据 (Y轴)
        # 即使某天没有数据，也要填 0，否则图表会断裂
        chart_dates = []
        chart_values = []

        for i in range(6, -1, -1):
            # 从6天前遍历到今天
            date_obj = today - datetime.timedelta(days=i)
            date_str = date_obj.strftime("%m-%d")

            chart_dates.append(date_str)
            chart_values.append(daily_counts.get(date_str, 0))

    # 查询workspace名称
    dep_query = db.query(Workspace).filter(Workspace.id == current_user.department_id).first()
    workspace_name = dep_query.name if dep_query else "公共区"

    return {
        "metrics": {
            "total_docs": total_docs,
            "total_chats": total_chats,
            "user_count": db.query(User).count() if current_user.role == "admin" else 0,
            "dept_name": workspace_name
        },
        "charts": {
            "file_types": [
                {"name": k, "value": v} for k, v in type_stats.items() if v > 0
            ],
            "activity": {
                "dates": chart_dates,
                "counts": chart_values
            }
        },
        "recent_docs": recent_docs_data
    }
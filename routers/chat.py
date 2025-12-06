"""
模块：routers.chat

本模块定义了与聊天功能相关的 API 接口。

包含的端点：处理聊天请求、列出会话、获取指定会话的消息以及删除会话。

作者：Guo Lijian
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
import json
import uuid
import datetime

# 引入我们拆分出去的模块
from dependencies import get_db, get_current_user
from models import User, ChatSession, ChatMessage
from rag_engine import get_vector_index, get_reranker # 引入 RAG 引擎

# LlamaIndex 相关依赖
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.llms import ChatMessage as LlamaChatMessage, MessageRole
from llama_index.core.vector_stores import MetadataFilter, MetadataFilters, FilterCondition

router = APIRouter(prefix="/api/chat", tags=["Chat"])

class ChatMsg(BaseModel):
    """表示单条聊天消息的模型（Pydantic）。

    字段：
    - role: 消息角色，通常为 "user" 或 "assistant"（字符串）
    - content: 消息文本内容
    """
    role: str
    content: str

class ChatRequest(BaseModel):
    """客户端发起的聊天请求模型（Pydantic）。

    字段：
    - messages: 消息列表，通常最后一条为当前输入的问题；
    - workspace_id: 工作区或部门 ID，默认 "default"；
    - stream: 是否使用流式响应，默认 True；
    - session_id: 可选，会话 ID，未提供则创建新会话。
    """
    messages: List[ChatMsg]
    workspace_id: str = "default"
    stream: bool = True
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    """示例响应模型（非流式返回时使用）。

    字段：
    - answer: 最终回答文本；
    - sources: 引用来源列表（文件名或片段标识）。
    """
    answer: str
    sources: List[str]

@router.post("")
async def chat_endpoint(
        request: ChatRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """处理聊天请求、管理会话并以流式方式返回响应。"""
    # ==========================================
    # 1. 会话管理逻辑 (持久化第一步)
    # ==========================================
    session_id = request.session_id
    current_session = None
    is_new_session = False
    last_message_content = request.messages[-1].content

    # 尝试查找现有会话
    if session_id:
        current_session = db.query(ChatSession).filter(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user.id
        ).first()

    # 如果没传 ID 或找不到，则创建新会话
    if not current_session:
        is_new_session = True
        session_id = str(uuid.uuid4())
        # 取问题的前 20 个字作为标题
        first_q = request.messages[-1].content[:20]

        current_session = ChatSession(
            id=session_id,
            user_id=current_user.id,
            title=first_q
        )
        db.add(current_session)
        db.commit()
    else:
        # 更新活跃时间
        current_session.updated_at = datetime.datetime.utcnow()
        db.add(current_session)
        db.commit()

    # 保存用户的消息到数据库
    user_content = request.messages[-1].content
    db_user_msg = ChatMessage(
        session_id=session_id,
        role="user",
        content=user_content
    )
    db.add(db_user_msg)
    db.commit()

    # 前端不再上传之前的历史记录，后端从数据库加载上下文
    history_messages = []
    if session_id:
        # 1. 从数据库查询最近的 N 条记录（例如最近 10 条）
        # 注意：要排除刚插入的那条当前用户消息，否则会重复；
        # 或者简单地查询所有，LlamaIndex 会把最后一条作为当前查询来处理。

        # 这里查询该会话的历史记录（不包含刚刚存入的最新一条用户消息，因为聊天引擎会自动把当前输入拼接到最后）
        recent_msgs = db.query(ChatMessage).filter(
            ChatMessage.session_id == session_id
        ).order_by(ChatMessage.created_at.desc()).limit(10).all()

        # 因为按时间倒序查询，需要反转为时间正序
        recent_msgs.reverse()

        # 2. 转换为 LlamaIndex 的消息对象
        for msg in recent_msgs:
            # 跳过刚存入的最新一条用户消息（因为流式接口的参数即为当前消息）
            # 通过比较内容是否相同来判断，也可以采用更严格的判断逻辑
            # 最佳实践：这里只加载“历史”，不要加载“当前”。
            if msg.content == request.messages[-1].content and msg.role == 'user':
                continue

            role = MessageRole.USER if msg.role == "user" else MessageRole.ASSISTANT
            history_messages.append(LlamaChatMessage(role=role, content=msg.content))

    # ==========================================
    # 2. 权限与 RAG 引擎初始化（保持原有逻辑）
    # ==========================================
    user_dept_id = current_user.department_id
    if not user_dept_id:
        filters = MetadataFilters(filters=[MetadataFilter(key="workspace_id", value="global")])
    else:
        filters = MetadataFilters(
            filters=[
                MetadataFilter(key="workspace_id", value=user_dept_id),
                MetadataFilter(key="workspace_id", value="global"),
            ],
            condition=FilterCondition.OR
        )

    # 管理员（admin）可以查看所有文档
    if current_user.role == "admin":
        filters = None

    try:
        # 获取向量索引（假设全局函数返回已加载的索引）
        index = get_vector_index()

        # 初始化会话记忆
        memory = ChatMemoryBuffer.from_defaults(
            chat_history=history_messages,
            token_limit=3000
        )

        # 构建聊天引擎
        chat_engine = index.as_chat_engine(
            chat_mode="context",
            memory=memory,
            similarity_top_k=5,
            node_postprocessors=[get_reranker()],
            filters=filters,
            system_prompt=(
                "你是一个企业智能知识库助手。请根据检索到的上下文（Context）回答用户的问题。"
                "如果上下文中没有相关信息，或者上下文不包含答案，请直接回答：“抱歉，当前知识库中未找到相关内容。”"
                "请用中文回答。严禁使用英文除非是专业词汇或英文简写，严禁编造事实。"
                "回答要专业、简洁。"
            )
        )

        # 执行流式对话
        response_stream = await chat_engine.astream_chat(last_message_content)

        # ==========================================
        # 4. 生成器逻辑 (增加存库逻辑)
        # ==========================================
        async def event_generator():
            # 如果是新会话，先把 session_id 发给前端，让前端更新地址栏或页面路由
            if is_new_session:
                yield json.dumps({"type": "session_id", "data": session_id}) + "\n"

            # 收集 AI 回复的全量数据
            full_ai_response = ""
            db_source_list = []  # 存入数据库的完整来源信息（含文本片段）
            frontend_source_list = []  # 发给前端展示的精简来源信息

            # 提取检索到的引用来源
            raw_nodes = response_stream.source_nodes
            seen_files = set()
            has_valid_nodes = False
            # 如果所有节点的评分都很低（<0.15），只选择分数最高的一个；否则保留评分 >= 0.15 的节点
            raw_nodes = sorted(raw_nodes, key=lambda n: n.score or 0.0, reverse=True)
            if raw_nodes and (raw_nodes[0].score or 0.0) < 0.15:
                raw_nodes = [raw_nodes[0]] if (raw_nodes[0].score > 0.01) else []
            else:
                raw_nodes = [node for node in raw_nodes if (node.score or 0.0) >= 0.15]

            for node in raw_nodes:
                score = node.score or 0.0
                has_valid_nodes = True

                # 提取节点的元数据
                file_name = node.metadata.get("file_name", "未知文档")
                page_label = node.metadata.get("page_label", None)
                workspace_id = node.metadata.get("workspace_id", "")
                text_content = node.get_content(metadata_mode="none")
                chat_source = {
                    "file_name": file_name,
                    "workspace_id": workspace_id,
                    "text_chunk": text_content
                }

                # 1. 准备给前端去重展示
                if (workspace_id, file_name) not in seen_files:
                    frontend_source_list.append(chat_source)
                    seen_files.add((workspace_id, file_name))

                # 2. 准备存入数据库（用于前端高亮等功能）
                # 需要存下文本内容（片段），以便前端进行查找与高亮
                db_source_list.append({
                    "file_name": file_name,
                    "page": page_label,
                    "score": round(float(score), 4),
                    "workspace_id": workspace_id,
                    "text_chunk": node.get_content(metadata_mode="none")  # 核心：存下原文片段
                })

            # 先发送引用来源给前端
            yield json.dumps({"type": "sources", "data": frontend_source_list}) + "\n"

            if not has_valid_nodes and not frontend_source_list:
                # 可选：如果没有检索到文档，可以发送特定状态给前端
                pass

            # 按分片流式发送模型输出
            async for token in response_stream.async_response_gen():
                full_ai_response += token
                yield json.dumps({"type": "content", "data": token}) + "\n"

            # ==========================================
            # 🔥 5. 流结束：保存【AI】的消息到数据库
            # ==========================================
            try:
                # 此时数据库会话通常还未关闭，如发生错误请检查数据库会话的生命周期管理
                db_ai_msg = ChatMessage(
                    session_id=session_id,
                    role="assistant",
                    content=full_ai_response,
                    sources=db_source_list  # 存入 JSONB 字段
                )
                db.add(db_ai_msg)
                db.commit()
            except Exception as e:
                print(f"❌ 保存 AI 消息失败: {e}")
                # 不抛出异常，以免打断前端显示

        return StreamingResponse(event_generator(), media_type="application/x-ndjson")

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# 1. 获取左侧会话列表
@router.get("/sessions")
async def get_sessions(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """获取当前用户的会话列表（按更新时间倒序）。"""
    sessions = db.query(ChatSession).filter(
        ChatSession.user_id == current_user.id
    ).order_by(ChatSession.updated_at.desc()).all()
    return sessions

# 2. 获取某个会话的详细消息
@router.get("/sessions/{session_id}")
async def get_session_messages(
        session_id: str,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """获取指定会话的所有消息（按时间正序）。"""
    # 鉴权：只能查看自己的会话
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == current_user.id
    ).first()
    if not session:
        raise HTTPException(404, "会话不存在")

    # 按时间正序查询消息
    msgs = db.query(ChatMessage).filter(
        ChatMessage.session_id == session_id
    ).order_by(ChatMessage.created_at.asc()).all()

    # 对 assistant 消息的 sources 列表按 workspace_id + file_name 去重，只保留第一次出现的来源
    for msg in msgs:
        if msg.role == "assistant" and msg.sources:
            unique_sources = []
            seen_sources = set()
            for source in msg.sources:
                source_key = (source.get("workspace_id"), source.get("file_name"))
                if source_key not in seen_sources:
                    unique_sources.append(source)
                    seen_sources.add(source_key)
            msg.sources = unique_sources

    return msgs

# 3. 删除会话
@router.delete("/sessions/{session_id}")
async def delete_session(
        session_id: str,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """删除指定会话及其关联的消息，仅允许会话所有者执行删除。"""
    session = db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id).first()
    if session:
        db.delete(session)
        db.commit()
    return {"status": "success"}
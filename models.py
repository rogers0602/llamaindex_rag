"""
本模块定义了应用程序的 SQLAlchemy ORM 模型。

它包含以下模型：
- Workspace：代表一个工作空间或部门。
- User：代表一个用户。
- DocumentRecord：代表一份文档记录。
- ChatSession：代表一个聊天会话。
- ChatMessage：代表一条聊天消息。

Author: Guo Lijian
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
import datetime
import uuid

# 1. 工作区/部门模型 (对应表 workspaces)
class Workspace(Base):
    __tablename__ = "workspaces"

    id = Column(String, primary_key=True, index=True)  # 如 '1', 'global', 'hr'
    name = Column(String, unique=True)
    description = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 反向关联：一个部门有多个用户
    users = relationship("User", back_populates="workspace")


# 2. 用户模型 (对应表 users)
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String, nullable=True)  # 本地用户必填，LDAP用户为空
    username = Column(String)

    # 关联部门
    department_id = Column(String, ForeignKey("workspaces.id"))
    workspace = relationship("Workspace", back_populates="users")

    role = Column(String, default="member")  # admin, member
    source = Column(String, default="local")  # local, ldap
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# 3. 文档模型 (对应表 documents)
class DocumentRecord(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String)
    file_size = Column(String)

    # 逻辑上的归属
    workspace_id = Column(String, index=True)
    is_global = Column(Boolean, default=False)

    # 🔥 新增：上传者关联
    uploader_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    uploader = relationship("User")

    upload_date = Column(DateTime(timezone=True), server_default=func.now())


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(Integer, ForeignKey("users.id"))
    # 会话标题，通常取第一句提问的前20个字
    title = Column(String, default="新会话")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # 关联消息
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("chat_sessions.id"))
    role = Column(String)  # 'user' | 'assistant'
    content = Column(Text)  # 对话内容

    # 🔥 关键：存引用来源，用于后续做 C 计划的高亮
    # 格式: [{"filename": "a.pdf", "page": 1, "score": 0.9, "text_chunk": "..."}]
    sources = Column(JSONB, nullable=True)

    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    session = relationship("ChatSession", back_populates="messages")
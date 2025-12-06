-- 启用向量扩展 (必须)
CREATE EXTENSION IF NOT EXISTS vector;

-- 工作区/部门表 (Workspaces)
CREATE TABLE IF NOT EXISTS workspaces (
    id VARCHAR(50) PRIMARY KEY, -- 例如 '1', '2', 'global'
    name VARCHAR(100) NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 初始化预设数据
INSERT INTO workspaces (id, name) VALUES
('global', '公共知识库'),
('d1968b24-1eee-47b6-b2e0-0f4d7de931f9', '研发部'),
('1e9047f5-e62d-4d4e-a3aa-cb42f450e052', '财务部'),
('d7056149-d38a-49e1-bcbf-4c231542afdb', '人力资源部')
ON CONFLICT (id) DO NOTHING;

-- 用户表 (Users)
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255), -- 本地密码存哈希，LDAP用户留空
    username VARCHAR(100) UNIQUE NOT NULL, -- 本地用户名，和 LDAP 用户一样也是唯一的
    department_id VARCHAR(50) REFERENCES workspaces(id),
    role VARCHAR(20) DEFAULT 'member', -- admin, editor, member
    is_active BOOLEAN DEFAULT TRUE,
    source VARCHAR(20) DEFAULT 'local', -- local, ldap
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO users (id, email, hashed_password, username, department_id, role) VALUES
-- 预设管理员用户 admin admin123
(1, 'admin@internal.com', '$pbkdf2-sha256$29000$VapV6l1rDSGkNAbgXIuRcg$g2xqIj8yrBv3TGECHZdRJ6INsOqrFt4MW8UXAkfw7bg',
'admin','global', 'admin')
ON CONFLICT (id) DO NOTHING;

-- 文档记录表 (Documents) - 存业务元数据
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    file_size VARCHAR(50),
    workspace_id VARCHAR(50) NOT NULL, -- 关联 workspace
    is_global BOOLEAN DEFAULT FALSE,
    content_hash VARCHAR(64), -- 用于防止重复上传
    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    uploader_id INTEGER
);

-- 索引优化
CREATE INDEX IF NOT EXISTS idx_docs_workspace ON documents(workspace_id);
CREATE INDEX IF NOT EXISTS idx_docs_global ON documents(is_global);

-- 创建会话表
CREATE TABLE IF NOT EXISTS chat_sessions (
    id VARCHAR(36) PRIMARY KEY,               -- UUID 字符串
    user_id INTEGER NOT NULL,                 -- 关联用户表
    title VARCHAR(255) DEFAULT '新会话',      -- 会话标题
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- 外键约束：关联到 users 表的 id
    CONSTRAINT fk_user
      FOREIGN KEY(user_id)
      REFERENCES users(id)
      ON DELETE CASCADE
);

-- 创建索引优化查询
CREATE INDEX idx_sessions_user_id ON chat_sessions(user_id);
CREATE INDEX idx_sessions_updated_at ON chat_sessions(updated_at DESC);

-- 创建消息表
CREATE TABLE IF NOT EXISTS chat_messages (
    id SERIAL PRIMARY KEY,                    -- 自增 ID
    session_id VARCHAR(36) NOT NULL,          -- 关联会话表
    role VARCHAR(50) NOT NULL,                -- 'user' 或 'assistant'
    content TEXT,                             -- 聊天内容
    sources JSONB DEFAULT '[]'::jsonb,        -- 存源文件信息 (为 Plan C 高亮做准备)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- 外键约束：关联到 chat_sessions 表的 id
    CONSTRAINT fk_session
      FOREIGN KEY(session_id)
      REFERENCES chat_sessions(id)
      ON DELETE CASCADE
);

CREATE INDEX idx_messages_session_id ON chat_messages(session_id);

-- 注意：向量表 (data_embeddings) 不需要手动建，LlamaIndex 会自动管理
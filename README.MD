
---

# 📚 Enterprise RAG Knowledge Base (Backend)

[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-009688.svg?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![LlamaIndex](https://img.shields.io/badge/LlamaIndex-0.10+-BC31EA.svg?style=flat)](https://www.llamaindex.ai/)
[![Ollama](https://img.shields.io/badge/Ollama-0.1.20+-000000.svg?style=flat&logo=ollama&logoColor=white)](https://ollama.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791.svg?style=flat&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg?style=flat&logo=docker&logoColor=white)](https://www.docker.com/)

基于 **LlamaIndex** 和 **FastAPI** 构建的企业级 RAG（检索增强生成）知识库后端系统。
支持完全私有化部署，具备多租户权限隔离、LDAP 统一认证、文档溯源高亮及会话持久化等企业级特性。
本项目是本人业余时间的开发成果，仅供学习交流使用，严禁商业用途（个人和企业可以免费使用）。

前端项目地址：[Enterprise RAG Knowledge Base (Frontend)](https://github.com/rogers0602/llamaindex_rag_front)

> **💡 说明**：本文档包含架构图和数据流图，推荐在 GitHub/GitLab 网页端查看，或在本地安装 Mermaid 预览插件。

---

## ✨ 核心特性

- **🔐 企业级安全架构**
  - **RBAC 权限控制**：基于角色的权限管理（管理员/普通成员）。
  - **多租户隔离**：通过 `workspace_id` 实现部门级数据物理/逻辑隔离。
  - **双模认证**：支持本地账号与 **LDAP/AD 域账号** 混合登录，自动同步组织架构。

- **🧠 全能型 RAG 引擎**
  - **Ollama 驱动**：LLM (`qwen2.5`) 和 Embedding (`bge-m3`) 均由 Ollama 服务统一管理，降低后端资源占用。
  - **精准重排序**：内置本地 **BGE-Reranker** 模型（打包于镜像中），大幅提升检索准确率。
  - **智能切片**：集成 PyMuPDF，支持 PDF/Word/Excel 等多格式文档的高精度解析与切分。

- **💬 深度交互体验**
  - **会话持久化**：完整保存历史对话记录，支持断点续聊。
  - **引用溯源**：返回精准的文档切片位置，支持前端 **PDF 原文高亮定位**。
  - **流式响应**：全异步 `StreamingResponse`，提供丝滑的打字机体验。

- **🐳 一键部署**
  - **开箱即用**：后端镜像内置 Reranker 模型，无需额外下载。
  - **容器编排**：提供完整的 `docker-compose.yml`，一键拉起全套服务。

---

# 🛡️ 产品特色

这是一个专为**数据安全敏感型企业**打造的 RAG（检索增强生成）知识库系统。
本项目旨在解决企业内部知识管理的痛点，提供**从底层模型到上层 UI 的全链路私有化解决方案**，确保数据不出域，断网环境亦可全功能运行。

## 🌟 核心亮点与技术选型

### 1. 💯 极致的私有化与离线能力 (Offline & Privacy First)
*   **无需联网**：系统内置所有依赖包与 AI 模型（Embedding/Rerank），支持在物理隔离的内网环境一键 Docker 部署。
*   **数据安全**：所有数据（向量、文档、对话日志）均存储在本地 PostgreSQL，无第三方 API 调用风险。

### 2. 🔐 严苛的权限隔离体系 (RBAC & Multi-Tenancy)
*   **部门级隔离**：实现了基于 `Workspace` 的多租户逻辑。研发部的文档，财务部不可见，从底层向量检索阶段即进行物理/逻辑隔离。
*   **无缝认证**：支持 **Local + LDAP/AD** 双模认证。企业域账号直接登录，自动同步组织架构，管理员可进行细粒度的人员与部门管理。

### 3. 🧠 经过实战验证的模型组合 (Model Strategy)
我们不盲目追求大参数，而是追求**效果与资源的最佳平衡**：
*   **LLM (Ollama)**：选用 `Qwen2.5` 系列。在中文理解、指令遵循上表现优异，且通过 Ollama 部署可大幅降低显存门槛。
*   **Embedding (Ollama/BGE-M3)**：选用 `BAAI/bge-m3`。
    *   *选择理由*：支持 **8192** 超长上下文（优于 BERT 的 512），完美适配长文档切片；具备 SOTA 级别的多语言与中文检索能力。
*   **Rerank (Local Python)**：内置 `BAAI/bge-reranker-base`。
    *   *选择理由*：这是 RAG 精度的关键。在向量粗排后进行精排，能有效解决“搜到了但相关性不高”的问题，显著减少大模型幻觉。

### 4. 📝 沉浸式交互体验 (UX & Feature)
*   **精准溯源高亮**：不同于普通的“显示引用文件”，本系统实现了**PDF/TXT 原文级高亮定位**。点击引用，弹窗自动滚动并高亮具体的段落，所见即所得。
*   **上下文记忆**：基于数据库持久化的会话管理，刷新不丢失。支持多轮对话，模型能理解“它”、“上面提到的”等指代词。
*   **全格式支持**：集成了 PyMuPDF 等解析器，支持 PDF、Word、Excel、Markdown 等多种格式的深度解析与智能切片。

### 5. 📊 数据洞察 (Dashboard)
*   提供可视化的**管理仪表盘**，管理员可实时监控知识库文档总量、问答活跃度趋势、文件类型分布及系统健康状态。

---

## 📸 预览 (Screenshots)
![系统概览](images/dashboard.png)
###### 管理人员可以看到所有人的上传文档以及问答活跃度趋势。而普通用户只能看到自己部门的文档和数据。
![带上下文的聊天，可以查询公共文档的内容](images/chat.png)
###### 聊天会话支持上下文记忆，刷新页面不会丢失历史记录。普通用户只能查询自己部门的文档和公共文档内容，管理员可以查询所有部门的文档内容。
![支持多种文档类型](images/chat2.png)
###### 研发部的只能查询研发部的文档以及公共文档的内容，财务部的只能查询财务部的文档以及公共文档的内容。
![点击引用来源文档可以预览文档并高亮关键字](images/chat3.png)
###### 点击“引用来源”可以在弹窗中预览对应的文档，并且高亮关键字，所见即所得。
![知识库](images/zsk.png)
###### 知识库页面可以查看自己部门的所有文档，管理员可以查看所有部门的文档。
###### 管理员可以删除所有文档，普通用户只能删除自己部门的文档。
###### 支持上传各种格式的文档，系统会自动解析并切片入库。如果上传的文档格式不支持解析，则会提示错误。
###### 如果上传的文档在本部门同名已存在，则会提示是否覆盖，防止重复上传。
###### 只有管理员可以上传公共文档，普通用户只能上传自己部门的文档。公共文档所有人可以查看。
![人员](images/person.png)
###### 管理员可以查看和管理所有部门和人员，普通用户看不到这个菜单。
###### 人员支持本地新建，也支持从 LDAP/AD 同步。如果是 LDAP/AD 账号，则无法修改密码。
###### 用户登录的时候先检查本地账号，如果不存在则去 LDAP/AD 验证，验证通过后自动创建本地账号。
###### 并在同步LDAP/AD时自动同步人员信息和部门信息。
![部门](images/depart.png)
###### 管理员可以新增、编辑、删除人员和部门，分配角色和权限。普通用户看不到这个菜单。
###### 部门支持本地新建，也支持从 LDAP/AD 同步。
###### 删除部门会同时删除该部门的所有人员，且无法恢复，请谨慎操作。
---

## 🏗️ 系统架构设计

### 1. 整体技术架构图

系统采用 **计算分离** 架构：Ollama 负责繁重的生成与向量化计算，Python 后端负责业务逻辑与轻量级重排序。

```mermaid
graph TD
    %% ==== Client Layer ====
    Client["前端（Vue3 / Web）"] -->|"REST API + Bearer Token"| Gateway["Nginx / FastAPI Router"]
    

    %% ==== Backend Core ====
    subgraph Backend_Service["后端服务（Python）"]
        Gateway --> Auth["认证模块（OAuth2 / LDAP）"]
        Gateway --> Manager["业务逻辑层"]

        %% ==== RAG Engine ====
        subgraph RAG_Engine["RAG 引擎（LlamaIndex）"]
            Manager --> Ingestion["文档解析与切片（PyMuPDF）"]
            Manager --> Retrieval["混合检索器（向量 + 关键词）"]
            Manager --> ChatEngine["对话引擎（Context Mode）"]
            
            Retrieval --> Reranker["本地重排序模型（BGE-Reranker）"]
            Ingestion --> EmbedModel["向量化模型（BGE-M3 Small）"]
        end
    end


    %% ==== Data Layer ====
    subgraph Data_Storage["数据存储"]
        PG["PostgreSQL（pgvector）"]
        FileSys["文件存储（files）"]
    end


    %% ==== External / Local Services ====
    subgraph External_Services["外部 / 本地服务"]
        Ollama["Ollama - Qwen2.5 模型服务"]
        LDAP["企业 LDAP / AD Server"]
    end


    %% ==== Cross-layer Connections ====
    Auth <--> LDAP
    Auth <--> PG
    Retrieval <--> PG

    Manager --> FileSys
    ChatEngine <--> Ollama
```

### 2. 0层数据流图 (DFD Level-0)

描述了用户与系统及其外部实体的核心数据交互流程。

```mermaid
graph LR
    %% ==== Actors ====
    User["普通用户"]
    Admin["管理员"]

    %% ==== System Core ====
    System["企业知识库后端系统"]

    %% ==== External Systems ====
    DB["PostgreSQL 数据库"]
    LLM["Ollama 模型服务"]
    LDAP["LDAP 认证源"]


    %% ==== User Interactions ====
    User -->|"1. 提问 / 查询"| System
    User -->|"2. 上传文档"| System
    Admin -->|"3. 用户 / 部门管理"| System

    %% ==== System Dependencies ====
    System -->|"4. 账号验证"| LDAP
    System -->|"5. 存取向量 / 元数据 / 历史记录"| DB
    System -->|"6. 生成回答（Context）"| LLM

    %% ==== Output ====
    System -->|"7. 返回答案 + 引用来源"| User
```

---

## 🛠️ 技术栈

*   **Runtime**: Python 3.10+
*   **Web Framework**: FastAPI
*   **RAG Framework**: LlamaIndex (v0.10+)
*   **Database**: PostgreSQL 16 (with `pgvector` extension)
*   **AI Engine**: 
    *   **Ollama**: 运行 `qwen2.5:3b` (Chat) 和 `bge-m3` (Embedding)
    *   **Local Python**: 运行 `BAAI/bge-reranker-base` (Rerank)
*   **Deployment**: Docker & Docker Compose

---
---

## 🚀 部署指南 (Docker)

### 前置条件
1.  宿主机安装 Docker & Docker Compose。
2.  宿主机安装 Ollama 并拉取模型：
    ```bash
    ollama pull qwen2.5:3b
    ollama pull bge-m3
    ```

### 1. 准备离线模型
为了实现 Rerank 功能的离线运行，请下载 `BAAI/bge-reranker-base` 模型文件放入 `backend/models/bge-reranker-base/` 目录。该目录会被打包进 Docker 镜像。

### 2. 启动服务
在项目根目录执行：

```bash
docker-compose up -d --build
```

### 3. 系统初始化
首次启动时，系统会自动执行以下初始化操作：
1.  **数据库**：自动创建表结构（包含向量表）。
2.  **组织架构**：创建默认公共部门 (`global`)。
3.  **管理员**：创建默认超级管理员账号。
    *   **账号**: `admin@internal.com`
    *   **密码**: `admin123` (请登录后立即修改)
---

## ⚙️ 环境配置 (Environment Variables)

核心配置位于 `docker-compose.yml` 或 `.env` 文件：

| 变量名 | 说明 | 默认值                      |
| :--- | :--- |:-------------------------|
| `DB_HOST` | 数据库地址 | `localhost:5432`         |
| `OLLAMA_BASE_URL` | Ollama 服务地址 | `http://localhost:11434` |
| `LDAP_SERVER` | LDAP 服务器地址 | `ldap://localhost:389`   |
| `EMBED_MODEL_NAME` | 嵌入模型名称 | `bge-m3`                 |
| `EMBEDDING_DIM` | 向量维度 | `1024` (对应 BGE-M3)       |

在 `docker-compose.yml` 中：

```yaml
environment:
  - DB_HOST=db
  - OLLAMA_BASE_URL=http://host.docker.internal:11434  # 指向宿主机 Ollama
  - EMBED_MODEL_NAME=bge-m3       # 指定 Ollama 中的模型名
  - EMBEDDING_DIM=1024            # BGE-M3 的维度
```

## 📂 项目结构说明

```text
backend/
├── main.py                # 程序入口，负责 App 组装
├── rag_engine.py          # LlamaIndex 核心配置 (单例模式)
├── dependencies.py        # FastAPI 依赖注入 (DB, Auth)
├── database.py            # 数据库连接池
├── models.py              # SQLAlchemy 数据模型
├── routers/               # 业务路由模块
│   ├── auth.py            # 登录认证
│   ├── chat.py            # 问答与会话管理
│   ├── documents.py       # 文档上传、解析与切片
│   ├── files.py           # 文件预览流 (支持断点续传)
│   ├── admin.py           # 部门人员管理
│   └── dashboard.py       # 统计报表数据
├── test/                  # 测试脚本目录
│   └── init_ldap_data.py  # 测试用 LDAP 初始化脚本
├── files/                 # 持久化文件存储目录
├── init_sql/              # PG数据库初始化目录
│   └── init.sql           # PG数据库初始化脚本
├── models/                # 本地 Reranker 模型 (构建时打入镜像)
├── .env                   # 环境变量配置文件
├── requirements.txt       # Python 依赖列表
├── docker-compose.yml     # 容器编排配置文件（LDAP是测试用的可以删除）
└── Dockerfile             # 容器构建描述文件
```

---

## 🧪 开发与调试

如果需要在本地 (非 Docker) 环境开发：

1.  **准备环境**:
    ```bash
    conda create -n rag_backend python=3.10
    conda activate rag_backend
    pip install -r requirements.txt
    ```
2.  **准备模型**:
    请确保 `backend/models/bge-reranker-base` 目录下有模型文件。
3.  **启动服务**:
    ```bash
    python main.py
    ```
    访问 Swagger 文档：`http://localhost:8000/docs`

---
## 开发计划及进度：（目前处于第一阶段开发中...）
---

### 🚀 第一阶段：生产级部署 (DevOps)

**目标**：一条命令 `docker-compose up -d` 拉起所有服务（前端+后端+数据库+Ollama+LDAP），且开机自启。

1.  **前端 Docker化**：
    *   编写前端 `Dockerfile`。
    *   使用 **多阶段构建**：第一阶段 `node` 环境进行 `npm run build`，第二阶段用 `nginx:alpine` 承载构建好的静态文件 (`dist` 目录)。
    *   配置 Nginx 反向代理，把 `/api` 请求转发给后端容器。

2.  **后端 Docker化**：
    *   编写后端 `Dockerfile`。
    *   **关键点**：把本地下载好的 `models/` 目录 COPY 进镜像，确保镜像在此处断网也能跑。
    *   安装依赖建议使用 `requirements.txt`。

3.  **编排优化 (`docker-compose.yml`)**：
    *   将前端、后端、Postgres、Ollama 全部网络互通。
    *   配置 `restart: always`。
    *   配置数据卷挂载（特别是 `uploads/` 目录和 `pg_data`），防止重启丢数据。

---

### 🧠 第二阶段：RAG 效果深度调优 (Data Centric AI)

现在的 RAG 能跑通，但面对复杂问题可能还不够精准。

1.  **混合检索 (Hybrid Search)**：
    *   **痛点**：纯向量检索对于“精确匹配”（如搜索合同号 `HT-2023-001` 或专有名词）效果很差。
    *   **方案**：引入 **BM25 关键词检索**。LlamaIndex 支持 PGVector 的混合检索模式。
    *   **实现**：同时进行 `Vector Search` + `Keyword Search`，然后用 `Reciprocal Rank Fusion (RRF)` 算法合并结果，最后再 ReRank。

2.  **元数据增强 (Metadata Extraction)**：
    *   **方案**：在上传文档时，让 LLM 自动提取摘要、关键词、年份等元数据存入数据库。
    *   **效果**：用户可以问“2023年的财务报表”，系统能通过 Metadata Filter 精准过滤年份，而不是靠语义去猜。

3.  **复杂文档解析 (LlamaParse / OCR)**：
    *   **痛点**：现在的方案对于扫描件 PDF 还是无能为力。
    *   **方案**：引入 OCR 引擎（如 PaddleOCR）或接入云端解析服务（如果允许的话），处理表格和扫描件。

---

### 📈 第三阶段：运营与反馈 (Product Features)

让系统“活”起来，不仅能查，还能进化。

1.  **后台日志与监控**：
    *   集成 **LangFuse** 或 **Arize Phoenix**（LlamaIndex 原生支持）。
    *   **效果**：可以看到每一个 Request 的完整链路：检索了哪些块？相似度多少？LLM 输入了什么？输出了什么？耗时多少？
    *   这是排查“为什么 AI 胡说八道”的终极工具。

2.  **知识库“重索引”功能**：
    *   **痛点**：如果哪天想换更强的 Embedding 模型（比如 BGE-M4），现在的数据库就废了。
    *   **方案**：在后台增加一个“重建索引”按钮。后台任务自动读取 `uploads/` 目录下的源文件，重新切片、重新 Embedding 入库。

---

🧾 许可证与商业使用
---
本项目采用 **AGPL-3.0** 许可证，这意味着：

 - 您可以自由地使用、修改和分发本项目，但必须遵守 AGPL-3.0 协议要求
 - **闭源商用需要购买商业授权**
 - 项目的**重要贡献者**可免费获得商业授权

强烈建议优先考虑AGPL-3.0合规方案。如有**商业授权**疑问，请邮件联系作者

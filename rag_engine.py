"""
此模块用于初始化 RAG 引擎。

它会设置语言模型、嵌入模型、重排序器和向量存储。
它使用 Ollama 作为大型语言模型和嵌入模型，并使用本地的 SentenceTransformer
进行重排序。向量存储使用带有 pgvector 扩展的 PostgreSQL 数据库。

Author: Guo Lijian
"""
import os
from llama_index.core import VectorStoreIndex, StorageContext
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.vector_stores.postgres import PGVectorStore
from llama_index.core import Settings
from llama_index.llms.ollama import Ollama
from llama_index.core.postprocessor import SentenceTransformerRerank

DB_NAME = os.getenv("DB_NAME", "knowledge_base")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PASS = os.getenv("DB_PASSWORD", "admin_password")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_USER = os.getenv("DB_USER", "admin")
EMBED_DIM = int(os.getenv("EMBEDDING_DIM", 1024))
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "qwen2.5:3b")
EMBED_MODEL_NAME = os.getenv("EMBED_MODEL_NAME", "BGE-M3") # BGE-M3 比较大效果更好但是很慢，如果嫌慢可以设置成nomic-embed-text


def init_settings():
    # 给它加个 keep_alive，让它聊完别急着退出，避免下次聊天又要加载
    print(f"⚙️ 连接 Ollama LLM 模型: {LLM_MODEL_NAME}...")
    Settings.llm = Ollama(
        model=LLM_MODEL_NAME,
        base_url=OLLAMA_BASE_URL,
        request_timeout=300.0,
        context_window=4096,
        keep_alive="1h", # 这里也设置一遍，双重保险
        additional_kwargs={"keep_alive": "1h"} # 兼容不同版本参数名称
    )
    print("✅ LLM 模型连接配置完成")
    # Embedding 模型加载
    print(f"⚙️ 连接 Ollama Embedding 模型: {EMBED_MODEL_NAME}...")
    Settings.embed_model = OllamaEmbedding(
        model_name=EMBED_MODEL_NAME,
        base_url=OLLAMA_BASE_URL,
        request_timeout=300.0,
        embed_batch_size=10
    )
    print("✅ Embedding 模型连接配置完成")


# 2. Reranker 单例
_reranker = None


def get_reranker():
    global _reranker
    if _reranker is None:
        print("⏳ 正在加载本地 Reranker 模型: bge-reranker-base...")
        model_path = "./models/bge-reranker-base"

        if not os.path.exists(model_path):
            # 兼容 Docker 路径或本地路径
            if os.path.exists("/app/models/bge-reranker-base"):
                model_path = "/app/models/bge-reranker-base"
            else:
                raise RuntimeError(f"❌ 找不到本地模型文件: {model_path}，请先下载！")

        _reranker = SentenceTransformerRerank(
            model=model_path,
            top_n=5
        )
        print("✅ 本地 Reranker 模型加载完成")
    return _reranker

# 3. Index 获取函数
_vector_index_instance = None

def get_vector_index():
    global _vector_index_instance

    # 2. 如果已经初始化过，直接返回，不再创建
    if _vector_index_instance is not None:
        return _vector_index_instance

    print("🔌 正在初始化向量数据库连接...")

    # 3. 初始化逻辑 (保持不变)
    vector_store = PGVectorStore.from_params(
        database=DB_NAME,
        host=DB_HOST,
        password=DB_PASS,
        port=DB_PORT,
        user=DB_USER,
        table_name="embeddings",
        embed_dim=EMBED_DIM
    )
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    # 4. 创建实例并赋值给全局变量
    _vector_index_instance = VectorStoreIndex.from_vector_store(
        vector_store=vector_store,
        storage_context=storage_context
    )

    print("✅ 向量索引加载完成 (Singleton)")
    return _vector_index_instance
"""
此模块定义了文档管理的API接口。

它包含用于上传、删除和列出文档的接口。

Author: Guo Lijian
"""
from fastapi import APIRouter
from llama_index.readers.file import (
    DocxReader,
    PyMuPDFReader,
    PptxReader,
    PandasExcelReader,
    PandasCSVReader,
    UnstructuredReader
)
from llama_index.core import (
    SimpleDirectoryReader,
)
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import NodeRelationship, RelatedNodeInfo
from dependencies import get_db, get_current_user
from fastapi import Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from models import User, DocumentRecord, Workspace
from rag_engine import get_vector_index
import os
import shutil

router = APIRouter(prefix="/api/documents", tags=["documents"])

# --- 文件解析器映射工厂 ---
def get_file_extractors():
    # 尝试初始化 UnstructuredReader (用于复杂格式)
    try:
        unstructured_reader = UnstructuredReader()
    except Exception:
        print("⚠️ Warning: UnstructuredReader 初始化失败，部分旧格式可能无法解析。请 pip install unstructured")
        unstructured_reader = None

    # 1. 显式指定需要特殊处理的格式
    file_extractor = {
        # 常用办公文档
        ".pdf": PyMuPDFReader(),
        ".docx": DocxReader(),
        ".pptx": PptxReader(),

        # 表格类 (使用 Pandas 读取，保留结构)
        ".xlsx": PandasExcelReader(pandas_config={"header": 0}),
        ".csv": PandasCSVReader(),
    }

    # 2. 如果安装了 Unstructured，支持更多格式
    if unstructured_reader:
        for ext in [".doc", ".ppt", ".xls", ".pages", ".numbers", ".key", ".eml", ".msg"]:
            file_extractor[ext] = unstructured_reader

    # 千万不要把 .txt, .md, .py 设为 None！
    # 直接不写它们，SimpleDirectoryReader 就会自动使用默认的 TextReader 正常处理。

    return file_extractor


# === 文件上传接口 ===
@router.post("/upload")
async def upload_file(
        file: UploadFile = File(...),
        is_public: bool = Form(False),
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    # 权限检查
    if is_public:
        if current_user.role != "admin":
            # 这里根据需求，如果你允许普通用户传公共文档可以去掉这个判断
            pass
        workspace_id = "global"
    else:
        workspace_id = current_user.department_id
        if not workspace_id:
            raise HTTPException(400, "你还没分配部门，无法上传")

    # 构造唯一 ID (用于向量库定位)
    unique_doc_id = f"{workspace_id}_{file.filename}"

    # 1. 检查 SQL 数据库是否存在同名记录
    existing_doc = db.query(DocumentRecord).filter(
        DocumentRecord.workspace_id == workspace_id,
        DocumentRecord.filename == file.filename,
        DocumentRecord.is_global == is_public
    ).first()

    if existing_doc:
        print(f"🔄 发现同名文件 '{file.filename}'，正在执行覆盖操作...")
        try:
            # 2. 删除旧的向量数据
            index = get_vector_index()
            index.delete_ref_doc(unique_doc_id, delete_from_docstore=True, delete_from_vector_store=True)
            print(f"   - 旧向量数据已清洗: {unique_doc_id}")

            # 3. 删除旧的 SQL 记录 (或者你可以选择 update，但 delete 再 add 更干净)
            db.delete(existing_doc)
            db.commit()  # 提交删除
            print(f"   - 旧数据库记录已删除")

        except Exception as e:
            print(f"⚠️ 覆盖旧文件失败: {e}")
            # 不阻断流程，继续尝试上传，或者选择 raise 报错
            raise HTTPException(500, "覆盖旧文件失败")

    # 1. 文件永久保存到服务器files目录下workspace子目录，以便后续下载查看
    store_dir = f"./files/{workspace_id}"
    if not os.path.exists(store_dir): os.makedirs(store_dir)

    file_ext = os.path.splitext(file.filename)[1].lower()
    file_path = os.path.join(store_dir, file.filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        print(f"📥 处理文件: {file.filename} ({file_ext}) -> PGVector")

        # 2. 🔥 读取文件 (使用 file_extractor)
        # 这一步会自动根据后缀名调用 Pandas, Unstructured 等解析器
        loader = SimpleDirectoryReader(
            input_files=[file_path],
            file_extractor=get_file_extractors()  # <--- 关键注入
        )
        documents = loader.load_data()

        if not documents:
            raise HTTPException(400, "文件解析为空，请检查文件内容是否可读")

        total_text_len = sum([len(d.text.strip()) for d in documents])
        if total_text_len < 10:
            # 如果读出来全是空的，抛出警告或错误
            # 这里的 status_code 400 会让前端 alert 错误信息
            raise HTTPException(status_code=400,
                                detail="无法读取文档文字。请确保上传的是【文字版PDF】而非【扫描图片版PDF】。")

        # 3. 🔥 给 Document 打标签 (Metadata)
        is_global_str = "true" if workspace_id == "global" else "false"

        for doc in documents:
            # 这里的 doc.id_ 是 LlamaIndex 内部的 ID，我们暂时不改它为 unique_doc_id
            # 因为一个 Excel 可能解析出多个 Doc (每个 Sheet 一个)，强制改成一样会覆盖
            # 我们主要依赖 node.ref_doc_id 和 metadata 来做删除

            doc.metadata["workspace_id"] = workspace_id
            doc.metadata["file_name"] = file.filename
            doc.metadata["file_key"] = unique_doc_id  # 存一个唯一 Key 方便后续查找
            doc.metadata["is_global"] = is_global_str
            doc.metadata["uploader_email"] = current_user.email

            # 排除不让大模型看到的 Metadata
            doc.excluded_llm_metadata_keys = ["workspace_id", "is_global", "file_key", "uploader_email", "file_name"]
            doc.excluded_embed_metadata_keys = ["workspace_id", "is_global", "file_key", "uploader_email", "file_name"]

        # 4. 切分并插入 Nodes
        # chunk_size: 每个片段的大小 (Token数)。256 约等于 300-400 个汉字。
        # chunk_overlap: 上下文重叠，防止切断句子。
        splitter = SentenceSplitter(
            chunk_size=512, # 把切片改大一点，可以让语义更连贯
            chunk_overlap=50
        )
        nodes = splitter.get_nodes_from_documents(documents)

        # 🔥 修复：使用 relationships 字典来设置父文档关联
        # 原来的 node.ref_doc_id = unique_doc_id 会报错，因为它是只读属性
        for node in nodes:
            node.relationships[NodeRelationship.SOURCE] = RelatedNodeInfo(node_id=unique_doc_id)

        index = get_vector_index()
        index.insert_nodes(nodes)

        print(f"✅ 成功插入 {len(nodes)} 个片段 (格式: {file_ext})")

        # 5. 存入 SQL 业务数据库
        size_mb = os.path.getsize(file_path) / (1024 * 1024)
        if size_mb < 1:
            size_str = f"{size_mb * 1024:.1f} KB"
        else:
            size_str = f"{size_mb:.2f} MB"

        new_doc = DocumentRecord(
            filename=file.filename,
            file_size=size_str,
            workspace_id=workspace_id,
            is_global=is_public,
            uploader_id=current_user.id
        )
        db.add(new_doc)
        db.commit()

        return {"status": "success", "filename": file.filename}

    except ImportError as e:
        print(f"❌ 缺少依赖库: {e}")
        raise HTTPException(500, f"服务器缺少解析该格式的依赖: {str(e)}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"❌ Upload Error: {e}")
        raise HTTPException(status_code=500, detail=f"解析失败: {str(e)}")


# ================= 删除接口 =================
@router.delete("/{doc_id}")
async def delete_document(
        doc_id: int,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    doc = db.query(DocumentRecord).filter(DocumentRecord.id == doc_id).first()
    if not doc:
        raise HTTPException(404, "文档不存在")

    can_delete = False
    if current_user.role == "admin":
        can_delete = True
    elif doc.workspace_id == current_user.department_id: # 同部门的人可以删除同部门的文档
        can_delete = True

    if not can_delete:
        raise HTTPException(status_code=403, detail="你无权删除此文档")

    try:
        index = get_vector_index()
        workspace_id = doc.workspace_id
        # 构造 ID
        unique_doc_id = f"{workspace_id}_{doc.filename}"

        print(f"🗑️ 删除向量引用: {unique_doc_id}")
        index.delete_ref_doc(unique_doc_id, delete_from_docstore=True, delete_from_vector_store=True)

        db.delete(doc)
        db.commit()

        # 删除文件
        file_path = f"./files/{workspace_id}/{doc.filename}"
        if os.path.exists(file_path):
            os.remove(file_path)

        return {"status": "success", "msg": "文档已删除"}

    except Exception as e:
        print(f"Delete Error: {e}")
        raise HTTPException(500, f"删除失败: {str(e)}")


# --- 列表接口 (补全字段) ---
@router.get("")
async def get_documents(
        workspace_id: str,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    # 1. 🔥 修正点：同时查询 DocumentRecord 对象 和 Workspace.name 字段
    query = db.query(DocumentRecord, Workspace.name)

    # 2. 🔥 修正点：使用 func.concat 处理 SQL 字符串拼接
    join_condition = DocumentRecord.workspace_id == Workspace.id

    # 3. 构造查询
    if current_user.role == "admin":
        # 管理员：查看所有，左连接获取部门名称
        docs = query.join(
            Workspace,
            join_condition,
            isouter=True
        ).order_by(DocumentRecord.upload_date.desc()).all()
    else:
        # 普通用户：过滤部门
        docs = query.join(
            Workspace,
            join_condition,
            isouter=True
        ).filter(
            (DocumentRecord.workspace_id == workspace_id) |
            (DocumentRecord.is_global == True)
        ).order_by(DocumentRecord.upload_date.desc()).all()

    result = []

    # 4. 🔥 现在 docs 里的每一项都是一个元组 (DocumentRecord对象, 部门名称字符串)
    # 所以这里可以解包了
    for doc, ws_name in docs:

        # 优化：处理 Global 文档 Join 不到的情况
        final_ws_name = ws_name
        if not final_ws_name:
            if doc.is_global or doc.workspace_id == 'global':
                final_ws_name = "公共知识库"
            else:
                final_ws_name = "未知部门"

        # 查询上传者信息 (这里还是会有 N+1 问题，但暂且保持原样)
        uploader_name = "Unknown"
        if doc.uploader_id:
            u = db.query(User).filter(User.id == doc.uploader_id).first()
            if u: uploader_name = u.username

        result.append({
            "id": str(doc.id),
            "name": doc.filename,
            "size": doc.file_size,
            "status": "indexed",
            "date": doc.upload_date.strftime("%Y-%m-%d"),
            "isGlobal": doc.is_global,
            "uploader_id": doc.uploader_id,
            "uploader_name": uploader_name,
            "workspace_name": final_ws_name  # 使用处理后的名称
        })

    return result
"""
此模块定义了用于身份验证的 API 端点。
它包含用于更改密码和登录的端点。
它支持本地认证和 LDAP 认证。

Author: Guo Lijian
"""
import os
from datetime import datetime, timedelta
from jose import jwt
from fastapi import Depends, HTTPException, status, APIRouter
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session
# 🔥 引入 SUBTREE 用于递归搜索
from ldap3 import Server, Connection, ALL, SUBTREE
import uuid

# 引入你的模型和数据库会话
from models import User, Workspace
from dependencies import get_db, get_current_user, verify_password, get_password_hash

# === 配置 ===
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "YOUR_SECRET_KEY_HERE")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440

# === 🔥 LDAP 配置 (适配 Docker OpenLDAP) ===
# 对应 docker-compose 里的配置
LDAP_SERVER = os.getenv("LDAP_SERVER", "ldap://localhost:389")
LDAP_BASE_DN = os.getenv("LDAP_BASE_DN", "dc=mycompany,dc=com")

# ⚠️ 注意：标准 LDAP 需要先用管理员账号搜索用户
# Docker osixia/openldap 的默认管理员 DN 是 cn=admin,dc=...
LDAP_ADMIN_DN = os.getenv("LDAP_ADMIN_DN", "cn=admin,dc=mycompany,dc=com")
LDAP_ADMIN_PASSWORD = os.getenv("LDAP_ADMIN_PASSWORD", "admin")

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


# --- LDAP 认证与自动同步 (OpenLDAP 版) ---
def authenticate_ldap_and_sync(username, password, db: Session):
    try:
        # 1. 【管理员绑定】连接 LDAP 服务器
        # 这一步是为了去“搜索”用户在哪，因为我们不知道用户属于哪个部门 (ou)
        server = Server(LDAP_SERVER, get_info=ALL)
        conn = Connection(server, user=LDAP_ADMIN_DN, password=LDAP_ADMIN_PASSWORD, auto_bind=True)

        # 2. 【搜索用户】根据 uid 查找用户
        # OpenLDAP 标准过滤器：(uid=zhangsan) 或 (cn=zhangsan)
        search_filter = f"(uid={username})"

        conn.search(
            search_base=LDAP_BASE_DN,
            search_filter=search_filter,
            # 获取 common name, email, 以及 entryDN (用于下一步验证)
            attributes=['cn', 'mail', 'entryDN'],
            search_scope=SUBTREE
        )

        if not conn.entries:
            print(f"❌ LDAP用户不存在: {username}")
            return None

        # 获取用户实体
        entry = conn.entries[0]
        user_dn = entry.entry_dn  # 获取用户的真实路径，例如: cn=zhangsan,ou=Tech,dc=mycompany...
        ldap_name = str(entry.cn) if entry.cn else username

        # 3. 【用户验证】使用查到的 user_dn 和用户输入的密码尝试重新连接
        # 这才是真正的密码校验步骤
        try:
            user_conn = Connection(server, user=user_dn, password=password, auto_bind=True)
            # 如果没有抛出异常，说明密码正确
            user_conn.unbind()
        except Exception:
            print(f"❌ LDAP密码错误: {username}")
            return None

        # 4. 【解析部门】从 DN 中提取 OU (Organizational Unit)
        # DN 样例: cn=zhangsan,ou=Tech,dc=mycompany,dc=com
        # 我们需要提取 "Tech"
        ldap_dept_name = "公共部门"  # 默认值
        dn_parts = user_dn.split(',')
        for part in dn_parts:
            # 去除空格并检查 ou= 开头
            clean_part = part.strip()
            if clean_part.lower().startswith("ou="):
                ldap_dept_name = clean_part.split('=')[1]
                break

        # 5. 【处理邮箱】
        if entry.mail:
            final_email = str(entry.mail)
        else:
            final_email = f"{username}@ldap.internal"

        print(f"✅ LDAP认证通过: {username} | 部门: {ldap_dept_name} | 邮箱: {final_email}")

        # --- 以下是数据库同步逻辑 (保持原逻辑优化) ---

        # A. 同步部门
        workspace = db.query(Workspace).filter(Workspace.name == ldap_dept_name).first()
        if not workspace:
            new_ws_id = f"ldap_{str(uuid.uuid4())[:8]}"  # 生成一个带前缀的ID
            workspace = Workspace(id=new_ws_id, name=ldap_dept_name, description="LDAP Synced")
            db.add(workspace)
            db.commit()
            db.refresh(workspace)

        # B. 同步用户 (使用 email 或 username 查找)
        # 优先用 email 查，防止重复
        user = db.query(User).filter(User.email == final_email).first()

        # 如果没查到，再尝试用 username 查一下 (防止之前的本地用户转 LDAP)
        if not user:
            user = db.query(User).filter(User.username == username).first()

        if not user:
            # 创建新用户
            user = User(
                email=final_email,
                username=ldap_name,  # 使用 LDAP 里的显示名
                hashed_password="",  # 本地不存真实密码
                department_id=workspace.id,
                role="member",
                source="ldap",
                is_active=True
            )
            db.add(user)
        else:
            # 更新用户信息 (同步 LDAP 的最新部门和名字)
            user.username = ldap_name
            user.department_id = workspace.id
            user.source = "ldap"
            # 如果之前是 local，现在转为 ldap，可以把密码置空或者保持原样
            user.hashed_password = ""  # 本地不存真实密码
            user.email = final_email  # 确保邮箱同步

        db.commit()
        db.refresh(user)
        return user

    except Exception as e:
        print(f"❌ LDAP 系统错误: {e}")
        return None

class ChangePasswordReq(BaseModel):
    old_password: str
    new_password: str


router = APIRouter(prefix="/api/auth", tags=["auth"])

@router.post("/change-password")
async def change_password(
    req: ChangePasswordReq,
    current_user: User = Depends(get_current_user), # 必须登录
    db: Session = Depends(get_db)
):
    # 1. 如果是 LDAP 用户，通常不允许在本地改密码（除非你有 AD 写权限）
    # 这里做一个简单的拦截，假设只有 source='local' 的才能改
    if current_user.source != "local":
        raise HTTPException(400, "域账号(LDAP)请联系管理员或在公司内部系统修改密码")

    # 2. 验证旧密码
    if not verify_password(req.old_password, current_user.hashed_password):
        raise HTTPException(400, "旧密码错误")

    # 3. 更新新密码
    current_user.hashed_password = get_password_hash(req.new_password)
    db.commit()

    return {"status": "success", "msg": "密码修改成功"}


# --- 登录接口 (支持本地和 LDAP 认证) ---
@router.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    login_input = form_data.username
    auth_user = None

    local_user = db.query(User).filter(User.username == login_input).first()
    if local_user and local_user.source == "local":
        if verify_password(form_data.password, local_user.hashed_password):
            auth_user = local_user

    if not auth_user:
        auth_user = authenticate_ldap_and_sync(login_input, form_data.password, db)

    if not auth_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    dept_name = auth_user.workspace.name if auth_user.workspace else "未分配部门"
    access_token = create_access_token(data={
        "sub": auth_user.email,
        "role": auth_user.role,
        "dept_id": auth_user.department_id,
        "uid": auth_user.id
    })

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_info": {
            "id": auth_user.id,
            "name": auth_user.username,
            "role": auth_user.role,
            "dept_name": dept_name,
            "dept_id": auth_user.department_id
        }
    }

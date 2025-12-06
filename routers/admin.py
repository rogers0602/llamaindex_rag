"""
本模块定义了管理员功能的API接口。
它包含用于管理部门和用户的接口。

Author: Guo Lijian
"""
from fastapi import APIRouter
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from models import User, Workspace
from dependencies import get_db, get_current_admin
from routers.auth import get_password_hash

router = APIRouter(prefix="/api/admin", tags=["admin"])

# 获取所有部门
@router.get("/departments")
async def get_departments(
        admin: User = Depends(get_current_admin),
        db: Session = Depends(get_db)
):
    # 排除 global 虚拟部门
    depts = db.query(Workspace).filter(Workspace.id != "global").all()

    # 统计每个部门的人数 (可选优化)
    result = []
    for d in depts:
        count = db.query(User).filter(User.department_id == d.id).count()
        result.append({
            "id": d.id,
            "name": d.name,
            "user_count": count,
            "created_at": d.created_at  # 假设有这个字段，没有可忽略
        })
    return result


# 添加部门
class DeptCreate(BaseModel):
    name: str


@router.post("/departments")
async def create_department(
        dept: DeptCreate,
        admin: User = Depends(get_current_admin),
        db: Session = Depends(get_db)
):
    # 检查重名
    if db.query(Workspace).filter(Workspace.name == dept.name).first():
        raise HTTPException(400, "部门名称已存在")

    # 生成 ID (简化起见用 uuid 或自增，这里假设用 uuid hex)
    import uuid
    new_id = str(uuid.uuid4())

    new_ws = Workspace(id=new_id, name=dept.name)
    db.add(new_ws)
    db.commit()
    return {"status": "success", "id": new_id, "name": dept.name}


# 删除部门 (级联删除人员)
@router.delete("/departments/{dept_id}")
async def delete_department(
        dept_id: str,
        admin: User = Depends(get_current_admin),
        db: Session = Depends(get_db)
):
    if dept_id == "global":
        raise HTTPException(400, "公共库不可删除")

    dept = db.query(Workspace).filter(Workspace.id == dept_id).first()
    if not dept:
        raise HTTPException(404, "部门不存在")

    # 🔥 级联删除逻辑：先删该部门下所有员工
    users_to_delete = db.query(User).filter(User.department_id == dept_id).all()
    deleted_count = len(users_to_delete)

    for u in users_to_delete:
        db.delete(u)  # 这里如果 User 表有关联文档，可能还需要处理文档，暂时只删人

    db.delete(dept)
    db.commit()

    return {"status": "success", "msg": f"已删除部门及旗下 {deleted_count} 名员工"}


# --- 3. 人员管理 API ---

# 获取所有人员
@router.get("/users")
async def get_users(
        admin: User = Depends(get_current_admin),
        db: Session = Depends(get_db)
):
    users = db.query(User).order_by(User.role, User.department_id, User.created_at.desc()).all()
    res = []
    for u in users:
        dept_name = "未分配"
        if u.department_id:
            ws = db.query(Workspace).filter(Workspace.id == u.department_id).first()
            if ws: dept_name = ws.name

        res.append({
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "role": u.role,
            "dept_name": dept_name,
            "dept_id": u.department_id
        })
    return res


# 添加人员
class UserCreate(BaseModel):
    username: str
    password: str
    department_id: str


@router.post("/users")
async def create_user(
        user_in: UserCreate,
        admin: User = Depends(get_current_admin),
        db: Session = Depends(get_db)
):
    # 检查用户名重复
    if db.query(User).filter(User.username == user_in.username).first():
        raise HTTPException(400, "用户名已存在")

    hashed_pw = get_password_hash(user_in.password)

    new_user = User(
        email=user_in.username + "@internal.com",  # 假设邮箱由用户名生成
        username=user_in.username,
        hashed_password=hashed_pw,
        role="member",  # 🔥 强制为 member
        department_id=user_in.department_id,
        source="local"
    )
    db.add(new_user)
    db.commit()
    return {"status": "success"}


# 删除人员
@router.delete("/users/{user_id}")
async def delete_user(
        user_id: int,
        admin: User = Depends(get_current_admin),
        db: Session = Depends(get_db)
):
    if user_id == admin.id:
        raise HTTPException(400, "不能删除自己")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "用户不存在")

    db.delete(user)
    db.commit()
    return {"status": "success"}
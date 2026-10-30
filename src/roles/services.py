from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.authentication.models import User
from src.roles.models import Role, user_roles
from src.roles.schemas import RoleCreate, RoleUpdate
from src.utils.redis import invalidate_document_list_cache


def list_roles(db: Session):
    return db.query(Role).order_by(Role.name).all()


def create_role(db: Session, data: RoleCreate):
    role = Role(name=data.name, description=data.description)
    db.add(role)

    try:
        db.commit()
        db.refresh(role)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Role already exists")

    invalidate_document_list_cache()
    return role


def update_role(db: Session, role_id: int, data: RoleUpdate):
    role = db.get(Role, role_id)

    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")

    updates = data.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="At least one field is required")
    if "name" in updates and updates["name"] is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Role name cannot be null")

    for field, value in updates.items():
        setattr(role, field, value)

    try:
        db.commit()
        db.refresh(role)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Role name already exists")

    invalidate_document_list_cache()
    return role


def delete_role(db: Session, role_id: int):
    role = db.get(Role, role_id)

    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")

    db.execute(user_roles.delete().where(user_roles.c.role_id == role_id))
    db.delete(role)
    db.commit()
    invalidate_document_list_cache()

    return {"message": "Role deleted successfully", "role_id": role_id}


def get_user_role_names(db: Session, user_id: int) -> list[str]:
    statement = select(Role.name).join(user_roles, Role.id == user_roles.c.role_id).where(user_roles.c.user_id == user_id)
    return list(db.execute(statement).scalars().all())


def assign_roles(db: Session, user_id: int, role_names: list[str]):
    user = db.get(User, user_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    normalized_names = list(dict.fromkeys(name.strip().lower() for name in role_names))

    if not normalized_names or any(not name for name in normalized_names):
        raise HTTPException(status_code=422, detail="At least one valid role is required")

    roles = db.query(Role).filter(Role.name.in_(normalized_names)).all()
    found_names = {role.name for role in roles}
    missing_names = set(normalized_names) - found_names

    if missing_names:
        raise HTTPException(status_code=404, detail=f"Roles not found: {', '.join(sorted(missing_names))}")

    try:
        db.execute(user_roles.delete().where(user_roles.c.user_id == user_id))

        for role in roles:
            db.execute(user_roles.insert().values(user_id=user_id, role_id=role.id))

        db.commit()
    except Exception:
        db.rollback()
        raise

    invalidate_document_list_cache()
    return {"user_id": user_id, "roles": sorted(found_names)}


def get_user_roles(db: Session, user_id: int):
    user = db.get(User, user_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {"user_id": user_id, "roles": get_user_role_names(db, user_id)}
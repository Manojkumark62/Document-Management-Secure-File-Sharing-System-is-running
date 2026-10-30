from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from src.database import get_db
from src.dependencies.roles import require_roles
from src.roles.schemas import RoleAssignment, RoleCreate, RoleResponse, RoleUpdate, UserRolesResponse
from src.roles.services import assign_roles, create_role, delete_role, get_user_roles, list_roles, update_role


router = APIRouter(prefix="/roles", tags=["Role Management"])


@router.post("/", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
def add_role(
    data: RoleCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin")),
):
    return create_role(db, data)


@router.get("/", response_model=list[RoleResponse])
def get_roles(
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin")),
):
    return list_roles(db)


@router.patch("/{role_id}", response_model=RoleResponse)
def edit_role(
    role_id: int,
    data: RoleUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin")),
):
    return update_role(db, role_id, data)


@router.delete("/{role_id}")
def remove_role(
    role_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin")),
):
    return delete_role(db, role_id)


@router.put("/users/{user_id}", response_model=UserRolesResponse)
def update_user_roles(
    user_id: int,
    data: RoleAssignment,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin")),
):
    return assign_roles(db, user_id, data.role_names)


@router.get("/users/{user_id}", response_model=UserRolesResponse)
def read_user_roles(
    user_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin")),
):
    return get_user_roles(db, user_id)
from typing import Callable

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.database import get_db
from src.dependencies.auth import get_current_user
from src.roles.services import get_user_role_names


def require_roles(*allowed_roles: str) -> Callable:
    def role_checker(
        current_user=Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        user_roles = get_user_role_names(db, current_user.id)

        if not set(allowed_roles).intersection(user_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this resource",
            )

        return current_user

    return role_checker
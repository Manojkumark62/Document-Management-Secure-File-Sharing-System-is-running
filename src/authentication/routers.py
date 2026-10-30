from fastapi import APIRouter, Depends, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from src.database import get_db
from src.authentication.models import User
from src.authentication.schemas import UserCreate, UserResponse, UserLogin, Token
from src.authentication.services import register_user, authenticate_user
from src.dependencies.roles import require_roles
from src.utils.rate_limit import enforce_login_rate_limit

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    return register_user(user_data, db)

@router.post("/login", response_model=Token)
def login(user_data: UserLogin, request: Request, db: Session = Depends(get_db)):
    enforce_login_rate_limit(request.client.host if request.client else "unknown")
    return authenticate_user(user_data, db)

@router.post("/token", response_model=Token, include_in_schema=False)
def oauth2_login(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    enforce_login_rate_limit(request.client.host if request.client else "unknown")
    user_data = UserLogin(username=form_data.username, password=form_data.password)
    return authenticate_user(user_data, db)

@router.get("/me", response_model=UserResponse)
def get_my_profile(current_user: User = Depends(require_roles("admin", "manager", "user", "viewer"))):
    return current_user

@router.get("/protected")
def protected_route(current_user: User = Depends(require_roles("admin", "manager", "user", "viewer"))):
    return {"message": "You have accessed a protected API", "username": current_user.username, "user_id": current_user.id}
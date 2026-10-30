from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status
from src.authentication.models import User
from src.authentication.schemas import UserCreate, UserLogin
from src.utils.hashing import hash_password, verify_password
from src.utils.jwt_handle import create_access_token

def register_user(user_data: UserCreate, db: Session) -> User:
    existing_user = db.query(User).filter((User.username == user_data.username) | (User.email == str(user_data.email))).first()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username or email already registered")
    new_user = User(username=user_data.username, email=str(user_data.email), hashed_password=hash_password(user_data.password))
    db.add(new_user)
    try:
        db.commit()
        db.refresh(new_user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username or email already registered")
    return new_user

def authenticate_user(user_data: UserLogin, db: Session) -> dict:
    user = db.query(User).filter(User.username == user_data.username).first()
    if not user or not verify_password(user_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password", headers={"WWW-Authenticate": "Bearer"})
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is inactive")
    access_token = create_access_token({"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

def get_user_by_username(username: str, db: Session) -> User:
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user
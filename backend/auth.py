import re
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from fastapi import Request, HTTPException
from backend.database import SessionLocal
from backend import models

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# =========================
# Password Validation
# =========================

def validate_password(password: str):

    if len(password) < 8:
        return "Password must be at least 8 characters long."

    if not re.search(r"[A-Z]", password):
        return "Password must contain at least one uppercase letter."

    if not re.search(r"[a-z]", password):
        return "Password must contain at least one lowercase letter."

    if not re.search(r"[0-9]", password):
        return "Password must contain at least one number."

    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return "Password must contain at least one special character."

    return None


# =========================
# Hashing Utilities
# =========================

def hash_password(password: str) -> str:
    return pwd_context.hash(password[:72])


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password[:72], hashed_password)


# =========================
# Authenticate
# =========================

def authenticate_user(db: Session, username: str, password: str):
    user = db.query(models.User).filter(models.User.username == username).first()

    if not user:
        return None

    if not verify_password(password, user.hashed_password):
        return None

    return user


# =========================
# Create User
# =========================
import re

def create_user(db, first_name, last_name, username, email,
                password, confirm_password, department, role):

    # Username validation
    if len(username) < 4:
        return "Username must be at least 4 characters long."

    existing_user = db.query(models.User).filter(models.User.username == username).first()
    if existing_user:
        return "Username already exists."

    existing_email = db.query(models.User).filter(models.User.email == email).first()
    if existing_email:
        return "Email already registered."

    # Confirm password
    if password != confirm_password:
        return "Passwords do not match."

    # Password rules
    if len(password) < 8:
        return "Password must be at least 8 characters long."

    if not re.search(r"[A-Z]", password):
        return "Password must contain at least one uppercase letter."

    if not re.search(r"[a-z]", password):
        return "Password must contain at least one lowercase letter."

    if not re.search(r"[0-9]", password):
        return "Password must contain at least one number."

    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return "Password must contain at least one special character."

    # Create user
    new_user = models.User(
        first_name=first_name,
        last_name=last_name,
        username=username,
        email=email,
        department=department,
        hashed_password=hash_password(password),
        role=role
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return None
  

  


# =========================
# Current User
# =========================

def get_current_user(request: Request):

    user_id = request.cookies.get("user_id")

    if not user_id:
        raise HTTPException(status_code=401)

    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.id == int(user_id)).first()

        if not user:
            raise HTTPException(status_code=401)

        return user
    finally:
        db.close()
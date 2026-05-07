from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
from app.services import auth_service

router = APIRouter()

class LoginRequest(BaseModel):
    username: str
    password: str

class CreateUserRequest(BaseModel):
    username: str
    email: str
    password: str
    role: str = "analyst"

class UpdateUserRequest(BaseModel):
    email: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None
    active: Optional[bool] = None

def get_current_user(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Non authentifié")
    token = authorization.replace("Bearer ", "")
    user = auth_service.verify_token(token)
    if not user:
        raise HTTPException(401, "Token invalide ou expiré")
    return user

def require_admin(authorization: str = Header(None)):
    user = get_current_user(authorization)
    if user["role"] != "admin":
        raise HTTPException(403, "Accès réservé aux administrateurs")
    return user

@router.post("/login")
def login(req: LoginRequest):
    result = auth_service.login(req.username, req.password)
    if not result:
        raise HTTPException(401, "Identifiants incorrects")
    return result

@router.post("/logout")
def logout(authorization: str = Header(None)):
    if authorization and authorization.startswith("Bearer "):
        auth_service.logout(authorization.replace("Bearer ", ""))
    return {"logged_out": True}

@router.get("/me")
def me(authorization: str = Header(None)):
    return get_current_user(authorization)

@router.get("/users")
def list_users(authorization: str = Header(None)):
    require_admin(authorization)
    return {"users": auth_service.list_users()}

@router.post("/users")
def create_user(req: CreateUserRequest, authorization: str = Header(None)):
    require_admin(authorization)
    try:
        user = auth_service.create_user(req.username, req.email, req.password, req.role)
        return user
    except ValueError as e:
        raise HTTPException(400, str(e))

@router.patch("/users/{username}")
def update_user(username: str, req: UpdateUserRequest, authorization: str = Header(None)):
    require_admin(authorization)
    try:
        updates = {k: v for k, v in req.model_dump().items() if v is not None}
        return auth_service.update_user(username, updates)
    except ValueError as e:
        raise HTTPException(400, str(e))

@router.delete("/users/{username}")
def delete_user(username: str, authorization: str = Header(None)):
    require_admin(authorization)
    try:
        auth_service.delete_user(username)
        return {"deleted": True}
    except ValueError as e:
        raise HTTPException(400, str(e))

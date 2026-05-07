import hashlib, secrets, json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# ── Simple file-based user store (use PostgreSQL in production) ──
USERS_FILE = Path("users.json")

def _load_users() -> dict:
    if USERS_FILE.exists():
        return json.loads(USERS_FILE.read_text())
    # Create default admin on first run
    default = {
        "users": {
            "admin": {
                "id": "admin",
                "username": "admin",
                "email": "admin@dataiq.com",
                "password_hash": _hash("admin123"),
                "role": "admin",
                "created_at": datetime.now().isoformat(),
                "active": True
            }
        },
        "tokens": {}
    }
    _save_users(default)
    return default

def _save_users(data: dict):
    USERS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))

def _hash(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def _gen_token() -> str:
    return secrets.token_urlsafe(32)

# ── Auth functions ──
def login(username: str, password: str) -> Optional[dict]:
    data = _load_users()
    user = data["users"].get(username)
    if not user or not user["active"]:
        return None
    if user["password_hash"] != _hash(password):
        return None
    token = _gen_token()
    data["tokens"][token] = {
        "user_id": username,
        "expires": (datetime.now() + timedelta(hours=24)).isoformat()
    }
    _save_users(data)
    return {"token": token, "user": {k: v for k, v in user.items() if k != "password_hash"}}

def verify_token(token: str) -> Optional[dict]:
    if not token:
        return None
    data = _load_users()
    tok = data["tokens"].get(token)
    if not tok:
        return None
    if datetime.now() > datetime.fromisoformat(tok["expires"]):
        del data["tokens"][token]
        _save_users(data)
        return None
    user = data["users"].get(tok["user_id"])
    if not user or not user["active"]:
        return None
    return {k: v for k, v in user.items() if k != "password_hash"}

def logout(token: str):
    data = _load_users()
    data["tokens"].pop(token, None)
    _save_users(data)

def list_users() -> list:
    data = _load_users()
    return [{k: v for k, v in u.items() if k != "password_hash"} for u in data["users"].values()]

def create_user(username: str, email: str, password: str, role: str) -> dict:
    data = _load_users()
    if username in data["users"]:
        raise ValueError(f"Utilisateur '{username}' existe déjà")
    if role not in ("admin", "analyst", "viewer"):
        raise ValueError("Rôle invalide")
    user = {
        "id": username,
        "username": username,
        "email": email,
        "password_hash": _hash(password),
        "role": role,
        "created_at": datetime.now().isoformat(),
        "active": True
    }
    data["users"][username] = user
    _save_users(data)
    return {k: v for k, v in user.items() if k != "password_hash"}

def update_user(username: str, updates: dict) -> dict:
    data = _load_users()
    if username not in data["users"]:
        raise ValueError("Utilisateur introuvable")
    if "password" in updates:
        updates["password_hash"] = _hash(updates.pop("password"))
    data["users"][username].update(updates)
    _save_users(data)
    return {k: v for k, v in data["users"][username].items() if k != "password_hash"}

def delete_user(username: str):
    data = _load_users()
    if username == "admin":
        raise ValueError("Impossible de supprimer l'admin principal")
    data["users"].pop(username, None)
    _save_users(data)

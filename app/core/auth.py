import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from app.core.config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def _hash_password(password: str) -> str:
    return hashlib.sha256(f"bidpilot:{password}".encode()).hexdigest()


def verify_password(plain: str, hashed: str) -> bool:
    return _hash_password(plain) == hashed


# Mock users for MVP
MOCK_USERS = {
    "admin": {
        "id": "user_admin_001",
        "username": "admin",
        "password_hash": _hash_password("admin123"),
        "role": "admin",
        "display_name": "系统管理员",
    },
    "bid_manager": {
        "id": "user_bm_001",
        "username": "bid_manager",
        "password_hash": _hash_password("bid123"),
        "role": "project_admin",
        "display_name": "投标经理",
    },
    "writer": {
        "id": "user_wr_001",
        "username": "writer",
        "password_hash": _hash_password("write123"),
        "role": "writer",
        "display_name": "编制人员",
    },
    "reviewer": {
        "id": "user_rv_001",
        "username": "reviewer",
        "password_hash": _hash_password("review123"),
        "role": "reviewer",
        "display_name": "审核人员",
    },
}


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")


async def get_current_user(token: str = Depends(oauth2_scheme)):
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        username = payload.get("sub")
        if username and username in MOCK_USERS:
            return MOCK_USERS[username]
    except JWTError:
        pass
    return None


async def require_auth_detail(token: str = Depends(oauth2_scheme)):
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录")
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="令牌无效或已过期")
    username = payload.get("sub")
    user = MOCK_USERS.get(username or "")
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="令牌用户不存在")
    return user


async def require_auth(user=Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录或令牌已过期")
    return user


def require_role(*roles: str):
    async def checker(user=Depends(require_auth)):
        if user["role"] not in roles and user["role"] != "admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
        return user
    return checker

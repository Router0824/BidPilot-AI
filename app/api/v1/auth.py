from fastapi import APIRouter, HTTPException, Depends
from app.core.auth import MOCK_USERS, verify_password, create_access_token, require_auth_detail
from app.schemas import LoginRequest, APIResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
async def login(data: LoginRequest):
    user = MOCK_USERS.get(data.username)
    if not user or not verify_password(data.password, user["password_hash"]):
        raise HTTPException(401, "用户名或密码错误")

    token = create_access_token({"sub": data.username, "role": user["role"]})
    return APIResponse(data={
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "username": user["username"],
            "role": user["role"],
            "display_name": user["display_name"],
        },
    })


@router.get("/me")
async def me(user: dict = Depends(require_auth_detail)):
    return APIResponse(data={
        "id": user["id"],
        "username": user["username"],
        "role": user["role"],
        "display_name": user["display_name"],
    })

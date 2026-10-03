from fastapi import APIRouter, Depends, HTTPException

from app.agents import LLMGateway, MockLLMGateway, reload_llm_gateway, build_llm_gateway
from app.core.llm_errors import llm_error_message
from app.core.auth import require_role
from app.core.runtime_config import public_llm_config, save_runtime_llm_config, resolve_llm_config, get_runtime_llm_config
from app.schemas import APIResponse, LLMConfigUpdate

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/llm-config")
async def get_llm_config(user=Depends(require_role("admin"))):
    return APIResponse(data=public_llm_config())


@router.put("/llm-config")
async def update_llm_config(payload: LLMConfigUpdate, user=Depends(require_role("admin"))):
    data = payload.model_dump()
    if data["provider"] != "mock" and not (data.get("api_key") or public_llm_config().get("api_key_configured")):
        raise HTTPException(400, "启用真实模型前请填写 API Key")
    try:
        updated = save_runtime_llm_config(data)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    gateway = reload_llm_gateway()
    updated["active_model"] = getattr(gateway, "model", "mock-llm")
    updated["mode"] = "mock" if isinstance(gateway, MockLLMGateway) else "real"
    return APIResponse(data=updated)


@router.post("/llm-config/test")
async def test_llm_config(payload: LLMConfigUpdate | None = None, user=Depends(require_role("admin"))):
    try:
        runtime = resolve_llm_config(payload.model_dump()) if payload else get_runtime_llm_config()
        if runtime.provider not in ("mock", "none", "disabled") and not runtime.api_key:
            raise ValueError("尚未配置真实模型的 API Key")
        gateway = build_llm_gateway(runtime)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    if isinstance(gateway, MockLLMGateway):
        return APIResponse(data={
            "ok": True,
            "mode": "mock",
            "message": "当前为 Mock 模式，无需 API Key，可直接演示。",
        })
    if not isinstance(gateway, LLMGateway):
        raise HTTPException(400, "当前模型配置不可用")
    try:
        result = await gateway.call(
            "connection_test",
            [
                {"role": "system", "content": "Return JSON only."},
                {"role": "user", "content": "请返回 {\"ok\": true, \"message\": \"connected\"}"},
            ],
            response_schema="json",
            max_tokens=64,
            temperature=0,
        )
    except Exception as exc:
        raise HTTPException(400, llm_error_message(exc))
    if result.get("ok") is not True:
        raise HTTPException(400, "模型未通过结构化响应检查，返回的 ok 不是 true")
    actual_model = result.get("_llm", {}).get("model") or gateway.model
    return APIResponse(data={
        "ok": True,
        "mode": "real",
        "model": actual_model,
        "requested_model": gateway.model,
        "message": f"{actual_model}：连接与 JSON 响应验证通过",
        "usage": result.get("_llm", {}).get("usage", {}),
    })

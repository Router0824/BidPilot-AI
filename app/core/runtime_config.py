import json
import os
from dataclasses import dataclass
from typing import Any

from app.core.config import BASE_DIR, settings


CONFIG_PATH = os.environ.get(
    "BIDPILOT_RUNTIME_CONFIG_PATH",
    os.path.join(BASE_DIR, "bidpilot_runtime_config.json"),
)


@dataclass
class RuntimeLLMConfig:
    provider: str
    base_url: str | None = None
    model: str | None = None
    fast_model: str | None = None
    quality_model: str | None = None
    timeout_seconds: int | None = None
    cost_limit_per_project: float | None = None
    estimated_cost_per_1k_tokens: float | None = None
    api_key: str | None = None

    @property
    def api_key_configured(self) -> bool:
        return bool(self.api_key)


def _read_raw() -> dict[str, Any]:
    if not os.path.exists(CONFIG_PATH):
        return {}
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}


def _write_raw(data: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


def get_runtime_llm_config() -> RuntimeLLMConfig:
    llm = _read_raw().get("llm") or {}
    return RuntimeLLMConfig(
        provider=str(llm.get("provider") or settings.LLM_PROVIDER or "mock").lower(),
        base_url=llm.get("base_url") or settings.LLM_BASE_URL,
        model=llm.get("model") or settings.LLM_MODEL,
        fast_model=llm.get("fast_model") or settings.LLM_FAST_MODEL,
        quality_model=llm.get("quality_model") or settings.LLM_QUALITY_MODEL,
        timeout_seconds=int(llm.get("timeout_seconds") or settings.LLM_TIMEOUT_SECONDS),
        cost_limit_per_project=float(llm.get("cost_limit_per_project") or settings.LLM_COST_LIMIT_PER_PROJECT or 0.0),
        estimated_cost_per_1k_tokens=float(
            llm.get("estimated_cost_per_1k_tokens") or settings.LLM_ESTIMATED_COST_PER_1K_TOKENS or 0.0
        ),
        api_key=llm.get("api_key") or settings.LLM_API_KEY,
    )


def public_llm_config() -> dict[str, Any]:
    cfg = get_runtime_llm_config()
    return {
        "provider": cfg.provider,
        "base_url": cfg.base_url or "",
        "model": cfg.model or "",
        "fast_model": cfg.fast_model or "",
        "quality_model": cfg.quality_model or "",
        "timeout_seconds": cfg.timeout_seconds or 60,
        "cost_limit_per_project": cfg.cost_limit_per_project or 0.0,
        "estimated_cost_per_1k_tokens": cfg.estimated_cost_per_1k_tokens or 0.0,
        "api_key_configured": cfg.api_key_configured,
        "config_path": CONFIG_PATH,
    }


def save_runtime_llm_config(payload: dict[str, Any]) -> dict[str, Any]:
    data = _read_raw()
    existing = data.get("llm") or {}
    provider = str(payload.get("provider") or "mock").lower()
    api_key = payload.get("api_key")
    if api_key is None or api_key == "":
        api_key = existing.get("api_key")
    if provider in {"mock", "none", "disabled"}:
        api_key = ""

    data["llm"] = {
        "provider": provider,
        "base_url": payload.get("base_url") or "",
        "model": payload.get("model") or "",
        "fast_model": payload.get("fast_model") or "",
        "quality_model": payload.get("quality_model") or "",
        "timeout_seconds": int(payload.get("timeout_seconds") or 60),
        "cost_limit_per_project": float(payload.get("cost_limit_per_project") or 0.0),
        "estimated_cost_per_1k_tokens": float(payload.get("estimated_cost_per_1k_tokens") or 0.0),
        "api_key": api_key or "",
    }
    _write_raw(data)
    return public_llm_config()

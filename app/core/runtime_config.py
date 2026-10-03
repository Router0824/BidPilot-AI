import json
import os
from dataclasses import dataclass, asdict
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
    import tempfile
    directory = os.path.dirname(CONFIG_PATH) or "."
    os.makedirs(directory, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=directory)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        os.replace(temporary, CONFIG_PATH)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def get_runtime_llm_config() -> RuntimeLLMConfig:
    llm = _read_raw().get("llm") or {}
    return RuntimeLLMConfig(
        provider=str(llm.get("provider") or settings.LLM_PROVIDER or "mock").lower(),
        base_url=llm.get("base_url", settings.LLM_BASE_URL),
        model=llm.get("model", settings.LLM_MODEL),
        fast_model=llm.get("fast_model", settings.LLM_FAST_MODEL),
        quality_model=llm.get("quality_model", settings.LLM_QUALITY_MODEL),
        timeout_seconds=int(llm.get("timeout_seconds", settings.LLM_TIMEOUT_SECONDS)),
        cost_limit_per_project=float(llm.get("cost_limit_per_project", settings.LLM_COST_LIMIT_PER_PROJECT)),
        estimated_cost_per_1k_tokens=float(
            llm.get("estimated_cost_per_1k_tokens", settings.LLM_ESTIMATED_COST_PER_1K_TOKENS)
        ),
        api_key=llm.get("api_key", settings.LLM_API_KEY),
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


def resolve_llm_config(payload: dict[str, Any]) -> RuntimeLLMConfig:
    current = get_runtime_llm_config()
    provider = str(payload.get("provider") or "mock").lower()
    defaults = {"deepseek": "https://api.deepseek.com", "openai": "https://api.openai.com/v1"}
    base_url = (payload.get("base_url") or defaults.get(provider, "")).rstrip("/")
    current_url = (current.base_url or defaults.get(current.provider, "")).rstrip("/")
    api_key = (payload.get("api_key") or "").strip()
    if provider in {"mock", "none", "disabled"}:
        api_key = ""
    elif not api_key:
        if provider == current.provider and base_url == current_url:
            api_key = current.api_key
        if not api_key:
            raise ValueError("请填写 API Key；更换服务商或地址时必须重新输入")
    if provider == "custom" and (not base_url or not payload.get("model")):
        raise ValueError("自定义服务必须填写 Base URL 和模型名")
    return RuntimeLLMConfig(provider=provider, base_url=base_url,
        model=payload.get("model"), fast_model=payload.get("fast_model"), quality_model=payload.get("quality_model"),
        timeout_seconds=int(payload.get("timeout_seconds", 60)),
        cost_limit_per_project=float(payload.get("cost_limit_per_project", 0)),
        estimated_cost_per_1k_tokens=float(payload.get("estimated_cost_per_1k_tokens", 0)), api_key=api_key)


def save_runtime_llm_config(payload: dict[str, Any]) -> dict[str, Any]:
    config = resolve_llm_config(payload)
    data = _read_raw()
    data["llm"] = asdict(config)
    _write_raw(data)
    return public_llm_config()

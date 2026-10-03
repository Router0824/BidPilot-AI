import httpx


class LLMResponseError(RuntimeError):
    pass


def llm_error_message(error):
    if isinstance(error, httpx.TimeoutException):
        return "模型请求超时，请检查网络或增加超时时间"
    if isinstance(error, httpx.HTTPStatusError):
        status = error.response.status_code
        reasons = {400: "模型名或请求参数不受支持", 401: "API Key 无效或已失效",
                   402: "余额不足", 403: "没有模型访问权限", 404: "API 地址或模型不存在",
                   429: "请求限流或额度不足"}
        return f"模型服务返回 HTTP {status}：{reasons.get(status, '服务暂不可用')}"
    if isinstance(error, httpx.RequestError):
        return "无法连接模型服务，请检查 Base URL 和网络"
    if isinstance(error, LLMResponseError):
        return str(error)
    return "模型返回格式异常，请检查模型兼容性"

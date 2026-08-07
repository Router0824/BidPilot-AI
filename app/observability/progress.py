import asyncio
import contextvars
from collections import defaultdict, deque
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any


current_project_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("current_project_id", default=None)
current_node_name: contextvars.ContextVar[str | None] = contextvars.ContextVar("current_node_name", default=None)

_subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)
_history: dict[str, deque] = defaultdict(lambda: deque(maxlen=80))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def progress_context(project_id: str | None, node_name: str | None = None):
    project_token = current_project_id.set(project_id)
    node_token = current_node_name.set(node_name)
    try:
        yield
    finally:
        current_node_name.reset(node_token)
        current_project_id.reset(project_token)


async def publish_progress(
    project_id: str | None,
    phase: str,
    title: str,
    detail: str | None = None,
    node_name: str | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    if not project_id:
        return
    event = {
        "type": "agent.progress",
        "phase": phase,
        "title": title,
        "detail": detail,
        "node_name": node_name or current_node_name.get(),
        "payload": payload or {},
        "created_at": _now(),
    }
    _history[project_id].append(event)
    stale = []
    for queue in list(_subscribers[project_id]):
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            stale.append(queue)
    for queue in stale:
        _subscribers[project_id].discard(queue)


async def publish_current(
    phase: str,
    title: str,
    detail: str | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    await publish_progress(current_project_id.get(), phase, title, detail, current_node_name.get(), payload)


def subscribe(project_id: str) -> asyncio.Queue:
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    _subscribers[project_id].add(queue)
    for event in _history[project_id]:
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            break
    return queue


def unsubscribe(project_id: str, queue: asyncio.Queue) -> None:
    _subscribers[project_id].discard(queue)

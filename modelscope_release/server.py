import os
from pathlib import Path

from fastapi import Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.routing import Route

from app.main import app


FRONTEND_DIST = Path(os.environ.get("BIDPILOT_FRONTEND_DIST", "/app/frontend_dist"))


if FRONTEND_DIST.exists():
    app.router.routes = [
        route
        for route in app.router.routes
        if not (isinstance(route, Route) and route.path == "/" and "GET" in route.methods)
    ]

    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="frontend-assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def frontend_spa(full_path: str):
        if full_path.startswith(("api/", "health/", "docs", "openapi.json")):
            return Response(status_code=404)

        requested = FRONTEND_DIST / full_path
        if requested.is_file():
            return FileResponse(requested)
        return FileResponse(FRONTEND_DIST / "index.html")

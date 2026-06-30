from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.routing import APIRoute

from v2.api.routes import router as v2_router

app = FastAPI(title="BeePDF", version="2.0-local-demo")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/demo", include_in_schema=False)
def demo_ui():
    demo_path = Path(__file__).resolve().parent.parent / "docs" / "coursebee_demo_ui.html"
    return FileResponse(demo_path)


@app.get("/demo-ko", include_in_schema=False)
def demo_ui_ko():
    demo_path = Path(__file__).resolve().parent.parent / "docs" / "coursebee_demo_ui_ko.html"
    return FileResponse(demo_path)


if v2_router is not None:
    for route in v2_router.routes:
        if isinstance(route, APIRoute):
            app.add_api_route(
                route.path,
                route.endpoint,
                methods=list(route.methods or []),
                response_model=route.response_model,
                tags=route.tags,
                name=route.name,
                summary=route.summary,
                description=route.description,
            )

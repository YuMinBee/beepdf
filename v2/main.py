from __future__ import annotations

from fastapi import FastAPI
from fastapi.routing import APIRoute

from v2.api.routes import router as v2_router

app = FastAPI(title="BeePDF", version="2.0-local-demo")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


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

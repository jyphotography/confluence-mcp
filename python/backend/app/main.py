from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.db.session import init_db
from app.api.weekly import router as weekly_router


# Ensure `confluence-mcp/` is on PYTHONPATH so we can share code with MCP server.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(title="Weekly Progress API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(weekly_router, prefix=settings.api_prefix)
    return app


app = create_app()


@app.on_event("startup")
def _startup() -> None:
    init_db()


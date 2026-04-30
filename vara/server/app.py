"""
FastAPI application factory.

The full server lands in Phase 5. This module is import-clean now and exposes a
minimal app with route registration placeholders.
"""

from __future__ import annotations

from importlib import import_module

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from vara.server.routes import collections, config, query

eval_routes = import_module("vara.server.routes.eval")


def create_app() -> FastAPI:
    """Create the Vara API server."""
    app = FastAPI(
        title="Vara",
        description="Vector database debugger and visualizer.",
        version="0.1.0",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:7842",
            "http://127.0.0.1:7842",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(config.router, prefix="/api")
    app.include_router(collections.router, prefix="/api")
    app.include_router(query.router, prefix="/api")
    app.include_router(eval_routes.router, prefix="/api")
    return app


app = create_app()

__all__ = ["app", "create_app"]

"""FastAPI app factory for the backtester dashboard."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse

from pac.backtester.api.deps import BacktestManager
from pac.backtester.api.routes import research, runs, strategies
from pac.backtester.results.store import ResultStore


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage BacktestManager lifecycle — shut down executor on exit."""
    yield
    app.state.manager.shutdown()


def create_app(
    *,
    static_dir: Path | None = None,
) -> FastAPI:
    """Build the FastAPI application.

    Args:
        static_dir: Path to SPA build output (dist/). If None, only API
            routes are available. When used as a uvicorn factory, falls
            back to PAC_DASHBOARD_STATIC_DIR env var or default path.
    """
    if static_dir is None:
        env_dir = os.environ.get("PAC_DASHBOARD_STATIC_DIR")
        if env_dir:
            candidate = Path(env_dir)
            static_dir = candidate if candidate.is_dir() else None
        else:
            candidate = Path(__file__).parent.parent / "dashboard" / "dist"
            static_dir = candidate if candidate.is_dir() else None

    app = FastAPI(
        title="PAC Backtester API",
        version="0.1.0",
        lifespan=_lifespan,
    )

    # CORS — allow Vite dev server during development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Shared state
    manager = BacktestManager(store=ResultStore())
    app.state.manager = manager

    # API routes
    app.include_router(runs.router, prefix="/api")
    app.include_router(strategies.router, prefix="/api")
    app.include_router(research.router, prefix="/api")

    # SPA static files — must be last (catch-all)
    if static_dir is not None and static_dir.is_dir():
        assets_dir = static_dir / "assets"
        if assets_dir.is_dir():
            app.mount(
                "/assets",
                StaticFiles(directory=assets_dir),
                name="assets",
            )

        # Capture static_dir for the closure — resolve() once to
        # prevent symlink-based path-traversal bypasses.
        _resolved = static_dir.resolve()

        @app.get("/{path:path}")
        async def spa_fallback(path: str) -> FileResponse:
            """Serve static files from dist/ if they exist, else index.html."""
            candidate = _resolved / path
            if (
                path
                and not any(part.startswith(".") for part in Path(path).parts)
                and candidate.is_file()
                and _resolved in candidate.resolve().parents
            ):
                return FileResponse(candidate)
            return FileResponse(_resolved / "index.html")

    return app

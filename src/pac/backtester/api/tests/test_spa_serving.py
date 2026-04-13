"""Tests for SPA static file serving and security guards."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from pac.backtester.api.app import create_app


@pytest.fixture()
def spa_dir(tmp_path: Path) -> Path:
    """Create a minimal SPA dist/ structure."""
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>SPA</html>")
    (dist / "favicon.svg").write_text("<svg/>")
    assets = dist / "assets"
    assets.mkdir()
    (assets / "main.js").write_text("console.log('ok')")
    return dist


@pytest.fixture()
def app(spa_dir: Path) -> FastAPI:
    return create_app(static_dir=spa_dir)


@pytest.mark.asyncio
async def test_spa_fallback_returns_index(
    app: FastAPI,
) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        r = await client.get("/some/route")
        assert r.status_code == 200
        assert "SPA" in r.text


@pytest.mark.asyncio
async def test_static_file_served_directly(
    app: FastAPI,
) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        r = await client.get("/favicon.svg")
        assert r.status_code == 200
        assert "<svg" in r.text


@pytest.mark.asyncio
async def test_api_routes_not_shadowed(
    app: FastAPI,
) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        r = await client.get("/api/runs")
        assert r.headers.get("content-type", "").startswith(
            "application/json",
        )


@pytest.mark.asyncio
async def test_dotfiles_not_served(
    app: FastAPI,
    spa_dir: Path,
) -> None:
    (spa_dir / ".env").write_text("SECRET=bad")
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        r = await client.get("/.env")
        assert "SPA" in r.text


@pytest.mark.asyncio
async def test_nested_dotfiles_not_served(
    app: FastAPI,
    spa_dir: Path,
) -> None:
    """Dotfile guard covers all path parts, not just top-level."""
    sub = spa_dir / "subdir"
    sub.mkdir()
    (sub / ".env").write_text("SECRET=bad")
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        r = await client.get("/subdir/.env")
        assert "SPA" in r.text


@pytest.mark.asyncio
async def test_path_traversal_blocked(
    app: FastAPI,
) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        r = await client.get("/../../../etc/passwd")
        assert r.status_code == 200
        assert "SPA" in r.text

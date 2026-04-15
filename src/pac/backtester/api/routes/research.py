"""Routes for browsing research experiments, artifacts, and papers."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import markdown as md
import nh3
import structlog
import yaml
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, Response
from pydantic import BaseModel

from pac.backtester.api.deps import BacktestManager, get_manager
from pac.backtester.api.models import (
    ExperimentDetailResponse,
    ExperimentListResponse,
    ExperimentSummary,
    PaperListResponse,
    PaperSummary,
    StrategySnapshotListResponse,
    StrategySnapshotSummary,
)
from pac.backtester.research.manifest import ExperimentManifest

logger = structlog.get_logger()

router = APIRouter(prefix="/research")

# ── Security constants ──

_ALLOWED_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".md",
        ".json",
        ".csv",
        ".html",
        ".png",
        ".svg",
        ".jpg",
        ".jpeg",
        ".gif",
        ".yaml",
        ".yml",
        ".toml",
        ".py",
        ".txt",
    }
)

_SAFE_TAGS: set[str] = {
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "p",
    "a",
    "img",
    "ul",
    "ol",
    "li",
    "blockquote",
    "pre",
    "code",
    "em",
    "strong",
    "table",
    "thead",
    "tbody",
    "tr",
    "th",
    "td",
    "br",
    "hr",
    "del",
    "sup",
    "sub",
    "span",
    "div",
}

_SAFE_ATTRS: dict[str, set[str]] = {
    "a": {"href", "title"},
    "img": {"src", "alt", "title"},
    "code": {"class"},
    "span": {"class"},
    "div": {"class"},
}

_RESEARCH_DIR_ENV = "PAC_RESEARCH_DIR"

_MEDIA_TYPES: dict[str, str] = {
    ".json": "application/json",
    ".csv": "text/csv",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
}


# ── Internal parsing model ──


class StrategySnapshot(BaseModel):
    """Schema for strategy YAML files in research/strategies/."""

    strategy: str
    version: str | None = None
    description: str | None = None
    params: dict[str, Any] = {}


# ── Helpers ──


def _research_dir() -> Path:
    """Resolve the research/ directory.

    Checks PAC_RESEARCH_DIR env var first, falls back to CWD / research.
    """
    env = os.environ.get(_RESEARCH_DIR_ENV)
    if env:
        return Path(env).resolve()
    return Path.cwd() / "research"


def _get_manifest() -> ExperimentManifest:
    """FastAPI dependency for ExperimentManifest."""
    return ExperimentManifest(_research_dir() / "experiments")


_depends_manifest = Depends(_get_manifest)
_depends_manager = Depends(get_manager)


def _validate_file_path(base_dir: Path, requested_path: str) -> Path:
    """Validate and resolve a file path, preventing traversal attacks.

    Raises HTTPException(400) for invalid paths, HTTPException(404) for
    missing files.
    """
    parts = Path(requested_path).parts
    if any(p == ".." for p in parts):
        raise HTTPException(400, "Invalid path: '..' not allowed")
    if any(p.startswith(".") for p in parts):
        raise HTTPException(400, "Invalid path: hidden files not allowed")
    candidate = (base_dir / requested_path).resolve()
    if not candidate.is_relative_to(base_dir.resolve()):
        raise HTTPException(400, "Invalid path: outside allowed directory")
    if candidate.suffix.lower() not in _ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"File type '{candidate.suffix}' not allowed")
    if not candidate.is_file():
        raise HTTPException(404, "File not found")
    return candidate


def _render_markdown(text: str) -> str:
    """Render Markdown to HTML with sanitization."""
    raw_html = md.markdown(text, extensions=["tables", "fenced_code"])
    return nh3.clean(raw_html, tags=_SAFE_TAGS, attributes=_SAFE_ATTRS)


def _serve_file(file_path: Path, *, raw: bool = False) -> Response:
    """Serve a validated file with appropriate content type."""
    suffix = file_path.suffix.lower()

    if suffix == ".md":
        text = file_path.read_text(encoding="utf-8")
        if raw:
            return Response(content=text, media_type="text/plain")
        html = _render_markdown(text)
        return HTMLResponse(content=html)

    if suffix == ".html":
        content = file_path.read_text(encoding="utf-8")
        return HTMLResponse(
            content=content,
            headers={"Content-Security-Policy": "sandbox"},
        )

    media_type = _MEDIA_TYPES.get(suffix)
    if media_type:
        return FileResponse(
            path=file_path,
            media_type=media_type,
        )

    # Fallback for other allowed extensions
    return FileResponse(path=file_path, media_type="text/plain")


# ── Endpoints ──


@router.get("/experiments", response_model=ExperimentListResponse)
def list_experiments(
    status: str | None = Query(None, description="Filter by status"),
    tag: str | None = Query(None, description="Filter by tag"),
    strategy: str | None = Query(None, description="Filter by strategy name"),
    manifest: ExperimentManifest = _depends_manifest,
) -> ExperimentListResponse:
    """List all experiments with auto-computed state."""
    experiments = manifest.scan()

    if status is not None:
        experiments = [e for e in experiments if e.status == status]
    if tag is not None:
        experiments = [e for e in experiments if tag in e.tags]
    if strategy is not None:
        experiments = [e for e in experiments if e.strategy_name == strategy]

    summaries = [
        ExperimentSummary(
            id=e.id,
            slug=e.slug,
            title=e.title,
            status=e.status,
            strategy_name=e.strategy_name,
            tags=e.tags,
            created=e.created,
            concluded=e.concluded,
            artifact_count=len(e.artifacts),
            report_count=len(e.reports),
            result_file_count=len(e.result_files),
        )
        for e in experiments
    ]
    return ExperimentListResponse(experiments=summaries, total=len(summaries))


@router.get(
    "/experiments/{experiment_id}",
    response_model=ExperimentDetailResponse,
)
def get_experiment(
    experiment_id: str,
    manifest: ExperimentManifest = _depends_manifest,
    manager: BacktestManager = _depends_manager,
) -> ExperimentDetailResponse:
    """Get full experiment detail with linked run IDs."""
    state = manifest.get(experiment_id)
    if state is None:
        raise HTTPException(404, f"Experiment '{experiment_id}' not found")

    linked = manager.store.search(experiment_id=experiment_id)
    run_ids = [r.run_id for r in linked]

    readme_html: str | None = None
    readme_path = state.directory / "README.md"
    if readme_path.is_file():
        text = readme_path.read_text(encoding="utf-8")
        readme_html = _render_markdown(text)

    return ExperimentDetailResponse(
        id=state.id,
        slug=state.slug,
        title=state.title,
        hypothesis=state.hypothesis,
        status=state.status,
        strategy_name=state.strategy_name,
        strategy_params_file=state.strategy_params_file,
        tags=state.tags,
        created=state.created,
        concluded=state.concluded,
        artifacts=state.artifacts,
        reports=state.reports,
        result_files=state.result_files,
        linked_run_ids=run_ids,
        readme_html=readme_html,
    )


@router.get("/experiments/{experiment_id}/files/{path:path}")
def get_experiment_file(
    experiment_id: str,
    path: str,
    raw: bool = Query(False, description="Return raw content without rendering"),
    manifest: ExperimentManifest = _depends_manifest,
) -> Response:
    """Serve a file from an experiment directory."""
    state = manifest.get(experiment_id)
    if state is None:
        raise HTTPException(404, f"Experiment '{experiment_id}' not found")

    file_path = _validate_file_path(state.directory, path)
    return _serve_file(file_path, raw=raw)


@router.get("/papers", response_model=PaperListResponse)
def list_papers() -> PaperListResponse:
    """List research papers from research/papers/."""
    papers_dir = _research_dir() / "papers"
    if not papers_dir.exists():
        return PaperListResponse(papers=[])

    papers: list[PaperSummary] = []
    for entry in sorted(papers_dir.iterdir()):
        if not entry.is_dir():
            continue
        paper_md = entry / "paper.md"
        if not paper_md.is_file():
            continue

        title = entry.name
        text = paper_md.read_text(encoding="utf-8")
        heading_match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
        if heading_match:
            title = heading_match.group(1).strip()

        has_figures = (entry / "figures").is_dir() and any(
            (entry / "figures").iterdir()
        )

        papers.append(
            PaperSummary(
                slug=entry.name,
                title=title,
                has_figures=has_figures,
            )
        )

    return PaperListResponse(papers=papers)


@router.get("/papers/{slug}/files/{path:path}")
def get_paper_file(
    slug: str,
    path: str,
    raw: bool = Query(False, description="Return raw content without rendering"),
) -> Response:
    """Serve a file from a paper directory."""
    papers_dir = _research_dir() / "papers"
    paper_dir = papers_dir / slug
    if not paper_dir.is_dir():
        raise HTTPException(404, f"Paper '{slug}' not found")

    file_path = _validate_file_path(paper_dir, path)
    return _serve_file(file_path, raw=raw)


@router.get("/strategies", response_model=StrategySnapshotListResponse)
def list_strategy_snapshots() -> StrategySnapshotListResponse:
    """List strategy parameter snapshots from research/strategies/."""
    strategies_dir = _research_dir() / "strategies"
    if not strategies_dir.exists():
        return StrategySnapshotListResponse(snapshots=[])

    snapshots: list[StrategySnapshotSummary] = []
    for pattern in ("*.yaml", "*.yml"):
        for filepath in sorted(strategies_dir.glob(pattern)):
            if not filepath.is_file():
                continue
            try:
                data = yaml.safe_load(filepath.read_text(encoding="utf-8"))
                parsed = StrategySnapshot.model_validate(data)
                snapshots.append(
                    StrategySnapshotSummary(
                        filename=filepath.name,
                        strategy_name=parsed.strategy,
                        params=parsed.params,
                    )
                )
            except Exception:
                logger.warning(
                    "strategy_snapshot_malformed",
                    path=str(filepath),
                )
                continue

    return StrategySnapshotListResponse(snapshots=snapshots)

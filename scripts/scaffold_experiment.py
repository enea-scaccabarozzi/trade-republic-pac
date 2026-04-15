"""Scaffold a new research experiment directory from _template/.

Usage:
    python scripts/scaffold_experiment.py <name> [--title "Human Title"]

Example:
    python scripts/scaffold_experiment.py crisis_timing \
        --title "Crisis Timing Asymmetry"
"""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")

_RESEARCH_DIR = Path("research")
_EXPERIMENTS_DIR = _RESEARCH_DIR / "experiments"
_TEMPLATE_DIR = _EXPERIMENTS_DIR / "_template"


def _next_id(experiments_dir: Path) -> str:
    """Determine the next experiment ID by scanning existing directories."""
    if not experiments_dir.exists():
        return "001"

    max_id = 0
    for entry in experiments_dir.iterdir():
        if not entry.is_dir():
            continue
        if entry.name.startswith("_"):
            continue
        parts = entry.name.split("-", 1)
        try:
            num = int(parts[0])
            max_id = max(max_id, num)
        except ValueError:
            continue

    return f"{max_id + 1:03d}"


def scaffold_experiment(
    name: str,
    title: str | None = None,
    output_dir: Path | None = None,
) -> list[Path]:
    """Create a new experiment directory from _template/.

    Args:
        name: Experiment name in snake_case (e.g., crisis_timing_asymmetry).
        title: Human-readable title. Defaults to name with underscores replaced
               by spaces, title-cased.
        output_dir: Base directory for output. Defaults to repo root.

    Returns:
        List of created file paths.

    Raises:
        SystemExit: On validation errors.
    """
    if not _NAME_PATTERN.match(name):
        print(
            f"Error: '{name}' is not a valid experiment name. "
            "Use snake_case (e.g. crisis_timing)."
        )
        sys.exit(1)

    if title is None:
        title = name.replace("_", " ").title()

    slug = name.replace("_", "-")
    base = output_dir or Path(".")
    experiments_dir = base / _EXPERIMENTS_DIR

    # Check for slug collision with existing experiments
    if experiments_dir.exists():
        for entry in experiments_dir.iterdir():
            if not entry.is_dir() or entry.name.startswith("_"):
                continue
            parts = entry.name.split("-", 1)
            if len(parts) == 2 and parts[1] == slug:
                print(
                    f"Error: An experiment with slug '{slug}' "
                    f"already exists at {entry}. Aborting."
                )
                sys.exit(1)

    exp_id = _next_id(experiments_dir)
    dir_name = f"{exp_id}-{slug}"
    exp_dir = experiments_dir / dir_name

    # Read template files
    template_dir = base / _TEMPLATE_DIR
    toml_template = (template_dir / "experiment.toml").read_text(encoding="utf-8")
    explore_template = (template_dir / "explore.py").read_text(encoding="utf-8")

    today = date.today().isoformat()

    # Interpolate placeholders
    toml_content = (
        toml_template.replace("{id}", exp_id)
        .replace("{slug}", slug)
        .replace("{title}", title)
        .replace("{created}", today)
    )

    explore_content = (
        explore_template.replace("{title}", title)
        .replace("{id}", exp_id)
        .replace("{slug}", slug)
    )

    # Create experiment directory and files
    exp_dir.mkdir(parents=True, exist_ok=True)

    toml_path = exp_dir / "experiment.toml"
    toml_path.write_text(toml_content, encoding="utf-8")

    explore_path = exp_dir / "explore.py"
    explore_path.write_text(explore_content, encoding="utf-8")

    created: list[Path] = [toml_path, explore_path]

    for path in created:
        print(f"  Created: {path}")

    return created


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print('Usage: python scripts/scaffold_experiment.py <name> [--title "Title"]')
        sys.exit(1)

    exp_name = args[0]
    exp_title: str | None = None

    if "--title" in args:
        title_idx = args.index("--title")
        if title_idx + 1 < len(args):
            exp_title = args[title_idx + 1]
        else:
            print("Error: --title requires a value.")
            sys.exit(1)

    scaffold_experiment(exp_name, title=exp_title)

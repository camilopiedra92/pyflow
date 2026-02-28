from __future__ import annotations

from pathlib import Path


def scan_agent_packages(path: Path) -> list[Path]:
    """Scan a directory for agent packages (subdirs containing workflow.yaml).

    Returns a sorted list of package directory Paths. If the directory does
    not exist, returns an empty list.
    """
    if not path.exists():
        return []
    return sorted(
        d for d in path.iterdir()
        if d.is_dir() and (d / "workflow.yaml").exists()
    )

from __future__ import annotations

from pathlib import Path


def scan_directory(path: Path, extension: str = ".yaml") -> list[Path]:
    """Scan a directory for files with the given extension.

    Returns a sorted list of Path objects. If the directory does not exist,
    returns an empty list.
    """
    if not path.exists():
        return []
    return sorted(path.glob(f"*{extension}"))

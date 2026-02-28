from __future__ import annotations

from pathlib import Path

from pyflow.platform.registry.discovery import scan_agent_packages


def test_scan_agent_packages_finds_packages(tmp_path: Path) -> None:
    """scan_agent_packages() returns dirs containing workflow.yaml."""
    pkg1 = tmp_path / "agent_a"
    pkg1.mkdir()
    (pkg1 / "workflow.yaml").write_text("name: a\n")
    (pkg1 / "__init__.py").touch()

    pkg2 = tmp_path / "agent_b"
    pkg2.mkdir()
    (pkg2 / "workflow.yaml").write_text("name: b\n")
    (pkg2 / "__init__.py").touch()

    notpkg = tmp_path / "not_a_package"
    notpkg.mkdir()
    (notpkg / "__init__.py").touch()

    result = scan_agent_packages(tmp_path)
    names = [p.name for p in result]
    assert names == ["agent_a", "agent_b"]
    assert "not_a_package" not in names


def test_scan_agent_packages_empty_dir(tmp_path: Path) -> None:
    """Empty directory returns empty list."""
    assert scan_agent_packages(tmp_path) == []


def test_scan_agent_packages_nonexistent(tmp_path: Path) -> None:
    """Nonexistent directory returns empty list."""
    assert scan_agent_packages(tmp_path / "missing") == []

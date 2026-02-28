from __future__ import annotations

from pathlib import Path

from pyflow.platform.registry.discovery import scan_agent_packages, scan_directory


def test_scan_empty_directory(tmp_path: Path) -> None:
    """Scanning an empty directory returns an empty list."""
    result = scan_directory(tmp_path)
    assert result == []


def test_scan_finds_yaml_files(tmp_path: Path) -> None:
    """Scanning a directory with YAML files returns them sorted."""
    (tmp_path / "b_workflow.yaml").write_text("name: b")
    (tmp_path / "a_workflow.yaml").write_text("name: a")
    (tmp_path / "c_workflow.yaml").write_text("name: c")

    result = scan_directory(tmp_path)
    assert len(result) == 3
    assert result == sorted(result)
    assert all(p.suffix == ".yaml" for p in result)


def test_scan_ignores_non_yaml_files(tmp_path: Path) -> None:
    """Only files with the requested extension are returned."""
    (tmp_path / "workflow.yaml").write_text("name: ok")
    (tmp_path / "notes.txt").write_text("not a workflow")
    (tmp_path / "data.json").write_text("{}")

    result = scan_directory(tmp_path)
    assert len(result) == 1
    assert result[0].name == "workflow.yaml"


def test_scan_nonexistent_directory_returns_empty() -> None:
    """Scanning a directory that does not exist returns an empty list."""
    result = scan_directory(Path("/nonexistent/path/that/does/not/exist"))
    assert result == []


def test_scan_custom_extension(tmp_path: Path) -> None:
    """Scanning with a custom extension filters correctly."""
    (tmp_path / "config.yml").write_text("key: val")
    (tmp_path / "config.yaml").write_text("key: val")

    result = scan_directory(tmp_path, extension=".yml")
    assert len(result) == 1
    assert result[0].name == "config.yml"


# -- scan_agent_packages tests ------------------------------------------------


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

    # Not a package (no workflow.yaml)
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

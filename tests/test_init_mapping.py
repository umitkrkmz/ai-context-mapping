"""Tests for scripts/init_mapping.py: which paths the map must cover.

``.agentignore`` and git's local ``.git/info/exclude`` both remove a path from the map. The second holds
personal, never-committed files (notes, roadmaps) that a fresh clone does not have.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_init_mapping():
    spec = importlib.util.spec_from_file_location("init_mapping", ROOT / "scripts" / "init_mapping.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["init_mapping"] = module
    spec.loader.exec_module(module)
    return module


init_mapping = load_init_mapping()


def make_repo(tmp_path: Path, agentignore: str = "", exclude: str = "") -> Path:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "ROADMAP.md").write_text("# private\n", encoding="utf-8")
    (tmp_path / "build").mkdir()
    (tmp_path / "build" / "out.txt").write_text("", encoding="utf-8")
    if agentignore:
        (tmp_path / ".agentignore").write_text(agentignore, encoding="utf-8")
    if exclude:
        (tmp_path / ".git" / "info").mkdir(parents=True)
        (tmp_path / ".git" / "info" / "exclude").write_text(exclude, encoding="utf-8")
    return tmp_path


def scanned(root: Path) -> set:
    return {e.path for e in init_mapping.scan_tree(root, init_mapping.IgnoreMatcher.from_root(root))}


def test_local_exclude_removes_paths_from_the_map(tmp_path: Path) -> None:
    root = make_repo(tmp_path, agentignore="build/\n", exclude="# personal\nROADMAP.md\n")
    paths = scanned(root)
    assert "ROADMAP.md" not in paths
    assert not any(p.startswith("build") for p in paths)
    assert "src/app.py" in paths


def test_without_a_local_exclude_the_file_must_be_mapped(tmp_path: Path) -> None:
    root = make_repo(tmp_path, agentignore="build/\n")
    assert "ROADMAP.md" in scanned(root)


def test_local_exclude_works_without_an_agentignore(tmp_path: Path) -> None:
    root = make_repo(tmp_path, exclude="ROADMAP.md\n")
    paths = scanned(root)
    assert "ROADMAP.md" not in paths and "build/out.txt" in paths


def test_a_git_file_instead_of_a_directory_is_tolerated(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    (root / ".git").write_text("gitdir: ../elsewhere\n", encoding="utf-8")  # worktrees and submodules
    assert "ROADMAP.md" in scanned(root)


def test_test_maps_honors_the_local_exclude_too(tmp_path: Path, monkeypatch) -> None:
    from tests import test_maps

    root = make_repo(tmp_path, exclude="ROADMAP.md\n")
    monkeypatch.setattr(test_maps, "IGNORE_PATH", root / ".agentignore")
    monkeypatch.setattr(test_maps, "LOCAL_EXCLUDE_PATH", root / ".git" / "info" / "exclude")
    matcher = test_maps.load_matcher()
    assert matcher.is_ignored("ROADMAP.md", False)
    assert not matcher.is_ignored("src/app.py", False)


def test_an_undecodable_exclude_file_does_not_crash_the_scan(tmp_path: Path) -> None:
    root = make_repo(tmp_path, exclude="ROADMAP.md\n")
    (root / ".git" / "info" / "exclude").write_bytes(b"\xff\xfe junk\nROADMAP.md\n")
    assert "ROADMAP.md" not in scanned(root)

from __future__ import annotations

from pathlib import Path


def test_removed_provider_has_zero_current_project_references() -> None:
    root = Path(__file__).resolve().parents[2]
    banned = ("olla" + "ma", "qw" + "en")
    ignored_parts = {
        ".git",
        ".uv-cache",
        ".venv",
        "node_modules",
        "dist",
        "tmp",
        "work",
        "output",
    }
    suffixes = {
        ".py",
        ".ts",
        ".tsx",
        ".md",
        ".json",
        ".toml",
        ".yaml",
        ".yml",
        ".ps1",
        ".env",
        ".lock",
    }
    matches: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.casefold() not in suffixes:
            continue
        if ignored_parts.intersection(path.relative_to(root).parts):
            continue
        content = path.read_text(encoding="utf-8", errors="ignore").casefold()
        if any(term in content for term in banned):
            matches.append(str(path.relative_to(root)))
    assert matches == []

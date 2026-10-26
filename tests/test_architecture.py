"""Архитектурное правило: app/core не зависит от внешних библиотек (ТЗ, 6.2)."""

import ast
from pathlib import Path

FORBIDDEN = {
    "aiogram",
    "vkbottle",
    "httpx",
    "openai",
    "sqlalchemy",
    "gspread",
    "google",
    "aiosqlite",
    "alembic",
}
CORE = Path(__file__).resolve().parent.parent / "app" / "core"


def _imported_roots(path: Path) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            roots |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
    return roots


def test_core_does_not_import_forbidden_packages() -> None:
    for py in CORE.rglob("*.py"):
        bad = _imported_roots(py) & FORBIDDEN
        assert not bad, f"{py.relative_to(CORE.parent.parent)} импортирует {sorted(bad)}"


def test_core_does_not_import_other_app_layers() -> None:
    layers = {"adapters", "llm", "storage", "documents", "delivery", "integrations", "jobs"}
    for py in CORE.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("app."):
                assert node.module.split(".")[1] not in layers, f"{py.name}: {node.module}"

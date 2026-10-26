"""Архитектурное правило: app/core импортирует только разрешённое (ТЗ, 6.2 и решение этапа 1)."""

import ast
import sys
from pathlib import Path

# Белый список: стандартная библиотека и чистые библиотеки без сети, БД и платформ.
ALLOWED_THIRD_PARTY = {"pydantic", "yaml", "phonenumbers", "email_validator"}
OTHER_LAYERS = {"adapters", "llm", "storage", "documents", "delivery", "integrations", "jobs"}
CORE = Path(__file__).resolve().parent.parent / "app" / "core"


def _imports(path: Path) -> list[tuple[str, int]]:
    """Все абсолютные импорты файла: (полное имя модуля, номер строки)."""
    found: list[tuple[str, int]] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found += [(alias.name, node.lineno) for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.append((node.module, node.lineno))
    return found


def test_core_imports_only_whitelisted_packages() -> None:
    allowed = set(sys.stdlib_module_names) | ALLOWED_THIRD_PARTY | {"app"}
    for py in CORE.rglob("*.py"):
        for module, line in _imports(py):
            root = module.split(".")[0]
            assert root in allowed, f"{py.name}:{line} импортирует {module}"


def test_core_does_not_import_other_app_layers() -> None:
    for py in CORE.rglob("*.py"):
        for module, line in _imports(py):
            parts = module.split(".")
            if parts[0] == "app":
                assert len(parts) > 1 and parts[1] == "core", f"{py.name}:{line} -> {module}"
                assert parts[1] not in OTHER_LAYERS


def test_core_is_not_empty() -> None:
    assert len(list(CORE.rglob("*.py"))) > 20  # защита от ложной зелени при смене путей

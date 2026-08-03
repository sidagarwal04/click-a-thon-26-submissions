from __future__ import annotations

import ast
from pathlib import Path


def test_thesys_adapter_has_only_transport_and_domain_imports() -> None:
    source = Path("src/zentra_adapter_thesys/client.py").read_text()
    imports = {
        alias.name
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imports.update(
        node.module or ""
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ImportFrom)
    )
    forbidden = (
        "semantic",
        "repository",
        "audit",
        "subprocess",
        "mcp",
        "approval",
        "tools",
    )
    assert not any(token in value for value in imports for token in forbidden)
    assert not any("zentra_adapter_" in value for value in imports if value != "openai")

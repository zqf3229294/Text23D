from __future__ import annotations

import ast


class CodeValidationError(ValueError):
    pass


ALLOWED_IMPORT_ROOTS = {"cadquery", "math"}
BLOCKED_CALLS = {
    "__import__",
    "compile",
    "eval",
    "exec",
    "globals",
    "input",
    "locals",
    "open",
    "vars",
}
BLOCKED_NAMES = {
    "__builtins__",
    "__file__",
    "__loader__",
    "__package__",
    "__spec__",
    "ctypes",
    "multiprocessing",
    "os",
    "pathlib",
    "pickle",
    "shutil",
    "socket",
    "subprocess",
    "sys",
    "threading",
}


def validate_cadquery_code(code: str) -> None:
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        raise CodeValidationError(f"Python syntax error: {exc}") from exc

    has_build_model = any(
        isinstance(node, ast.FunctionDef) and node.name == "build_model"
        for node in tree.body
    )
    if not has_build_model:
        raise CodeValidationError("Generated code must define build_model().")

    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef):
            raise CodeValidationError("Async functions are not allowed in CAD scripts.")

        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                if root not in ALLOWED_IMPORT_ROOTS:
                    raise CodeValidationError(f"Import is not allowed: {alias.name}")

        if isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".", 1)[0]
            if root not in ALLOWED_IMPORT_ROOTS:
                raise CodeValidationError(f"Import is not allowed: {node.module}")

        if isinstance(node, ast.Name) and node.id in BLOCKED_NAMES:
            raise CodeValidationError(f"Blocked name used: {node.id}")

        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in BLOCKED_CALLS:
                raise CodeValidationError(f"Blocked function call: {node.func.id}()")
            if isinstance(node.func, ast.Attribute):
                root = _attribute_root(node.func)
                if root in BLOCKED_NAMES:
                    raise CodeValidationError(
                        f"Blocked module call through {root}.{node.func.attr}()."
                    )


def _attribute_root(node: ast.Attribute) -> str | None:
    current: ast.AST = node
    while isinstance(current, ast.Attribute):
        current = current.value
    if isinstance(current, ast.Name):
        return current.id
    return None

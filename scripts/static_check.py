#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_PARTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "node_modules",
    "venv",
}


def iter_paths(pattern: str) -> list[Path]:
    return sorted(
        path
        for path in ROOT.rglob(pattern)
        if not (set(path.relative_to(ROOT).parts) & SKIP_PARTS)
    )


def notebook_source(source: str | list[str]) -> str:
    if isinstance(source, list):
        source = "".join(source)
    lines = str(source).splitlines()
    first_index = next((idx for idx, line in enumerate(lines) if line.strip()), None)
    if first_index is not None and lines[first_index].lstrip().startswith("%%"):
        lines = lines[:first_index] + lines[first_index + 1:]

    cleaned: list[str] = []
    for line in lines:
        stripped = line.lstrip()
        lowered = stripped.lower()
        if stripped.startswith(("%", "!")):
            continue
        if lowered.startswith(("pip install ", "python -m pip ", "conda install ")):
            continue
        cleaned.append(line)
    return "\n".join(cleaned).strip() + "\n" if any(line.strip() for line in cleaned) else ""


def check_python(path: Path) -> None:
    ast.parse(path.read_text(encoding="utf-8"), filename=str(path.relative_to(ROOT)))


def check_notebook(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("nbformat") != 4:
        raise ValueError(f"unexpected notebook format: {data.get('nbformat')}")
    cells = data.get("cells")
    if not isinstance(cells, list) or not cells:
        raise ValueError("notebook has no cells")
    for index, cell in enumerate(cells, start=1):
        if "cell_type" not in cell:
            raise ValueError(f"cell {index} is missing cell_type")
        if cell.get("cell_type") != "code":
            continue
        source = notebook_source(cell.get("source", ""))
        if source:
            ast.parse(source, filename=f"{path.relative_to(ROOT)}:cell-{index}")


def check_requirements(require_pinned: bool, require_any: bool) -> None:
    paths = iter_paths("requirements*.txt")
    if require_any and not paths:
        raise ValueError("no requirements*.txt file found")
    for path in paths:
        deps = [
            line.strip()
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        if not deps:
            raise ValueError(f"{path.relative_to(ROOT)} has no dependencies")
        if require_pinned:
            for dep in deps:
                if "==" not in dep:
                    raise ValueError(f"{path.relative_to(ROOT)} dependency is not pinned: {dep}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-pinned-requirements", action="store_true")
    parser.add_argument("--require-notebook", action="store_true")
    parser.add_argument("--required-notebook", action="append", default=[])
    parser.add_argument("--required-requirements", action="append", default=[])
    args = parser.parse_args()

    failures: list[str] = []
    for path in iter_paths("*.py"):
        try:
            check_python(path)
        except Exception as exc:  # noqa: BLE001 - concise lint report
            failures.append(f"{path.relative_to(ROOT)}: {exc}")
    notebooks = iter_paths("*.ipynb")
    for required in args.required_notebook:
        if not (ROOT / required).is_file():
            failures.append(f"{required} is missing")
    if args.require_notebook and not notebooks:
        failures.append("no notebooks found")
    for path in notebooks:
        try:
            check_notebook(path)
        except Exception as exc:  # noqa: BLE001 - concise lint report
            failures.append(f"{path.relative_to(ROOT)}: {exc}")
    try:
        for required in args.required_requirements:
            if not (ROOT / required).is_file():
                failures.append(f"{required} is missing")
        check_requirements(
            args.require_pinned_requirements,
            bool(args.required_requirements),
        )
    except Exception as exc:  # noqa: BLE001 - concise lint report
        failures.append(str(exc))

    if failures:
        print("Static validation failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("Static validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

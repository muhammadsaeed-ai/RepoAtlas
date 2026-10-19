"""Bounded static analysis for Python repositories."""

from __future__ import annotations

import ast
import fnmatch
import os
import sys
import tokenize
from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from repoatlas import SCHEMA_VERSION, __version__
from repoatlas.errors import RepoAtlasError

EXCLUDED_DIRS = {
    ".git", ".hg", ".svn", ".venv", "venv", "env", "node_modules", "dist", "build",
    "target", ".tox", ".nox", ".mypy_cache", ".pytest_cache", ".ruff_cache", "__pycache__",
    "site-packages", "vendor", ".idea", ".vscode", ".repoatlas", "htmlcov",
}
EXCLUDED_FILES = {".DS_Store", "Thumbs.db", "repoatlas.json", "repoatlas.md", "repoatlas.svg"}
MAX_FILE_COUNT = 50_000
MAX_PYTHON_BYTES = 2 * 1024 * 1024
MAX_SINGLE_FILE_BYTES = 100 * 1024 * 1024
MAX_GRAPH_EDGES = 100_000


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _category(path: str) -> str:
    item = Path(path)
    parts = {part.lower() for part in item.parts}
    if "tests" in parts or item.name.startswith("test_") or item.name.endswith("_test.py"):
        return "test"
    if item.suffix.lower() in {".md", ".rst", ".adoc"} or "docs" in parts:
        return "documentation"
    if item.name.lower() in {"pyproject.toml", "setup.py", "setup.cfg", "tox.ini", "makefile", "dockerfile", ".gitignore", "license"} or item.suffix.lower() in {".toml", ".ini", ".cfg", ".yml", ".yaml", ".json"}:
        return "configuration"
    if item.suffix.lower() == ".py":
        return "python-source"
    if item.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico"}:
        return "image"
    return "other"


def _load_ignore_file(path: Path, base: str) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    rules: list[dict[str, Any]] = []
    for raw in lines:
        line = raw.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if line.startswith("\\#") or line.startswith("\\!"):
            line = line[1:]
        negate = line.startswith("!")
        if negate:
            line = line[1:]
        directory_only = line.endswith("/")
        anchored = line.startswith("/")
        line = line.strip("/")
        if line:
            rules.append({"pattern": line, "base": base, "negate": negate, "dir": directory_only, "anchored": anchored, "slash": "/" in line})
    return rules


def _matches_rule(rule: dict[str, Any], relative: str, is_dir: bool) -> bool:
    base = rule["base"]
    if base:
        if relative == base:
            candidate = ""
        elif relative.startswith(base + "/"):
            candidate = relative[len(base) + 1:]
        else:
            return False
    else:
        candidate = relative
    if not candidate:
        return False
    if rule["dir"] and not is_dir and "/" not in candidate:
        return False
    pattern = rule["pattern"]
    if rule["slash"] or rule["anchored"]:
        return fnmatch.fnmatchcase(candidate, pattern) or any(fnmatch.fnmatchcase("/".join(candidate.split("/")[:i]), pattern) for i in range(1, len(candidate.split("/"))))
    return any(fnmatch.fnmatchcase(part, pattern) for part in candidate.split("/"))


def _ignored(relative: str, is_dir: bool, rules: list[dict[str, Any]], extra: Iterable[str]) -> bool:
    parts = Path(relative).parts
    if any(part in EXCLUDED_DIRS for part in (parts if is_dir else parts[:-1])):
        return True
    if is_dir and parts and parts[-1] in EXCLUDED_DIRS:
        return True
    if not is_dir and parts and parts[-1] in EXCLUDED_FILES:
        return True
    ignored = False
    for pattern in extra:
        if fnmatch.fnmatchcase(relative, pattern) or fnmatch.fnmatchcase(Path(relative).name, pattern):
            ignored = True
    for rule in rules:
        if _matches_rule(rule, relative, is_dir):
            ignored = not rule["negate"]
    return ignored


def _module_name(relative: str, root_name: str) -> tuple[str, bool]:
    path = Path(relative)
    parts = list(path.with_suffix("").parts)
    is_package = path.name == "__init__.py"
    if is_package:
        parts = parts[:-1]
        if not parts:
            return root_name.replace("-", "_"), True
    parts = [part for part in parts if part]
    if not parts:
        return root_name.replace("-", "_"), False
    return ".".join(parts), is_package


def _main_guard(node: ast.AST) -> bool:
    if not isinstance(node, ast.If) or not isinstance(node.test, ast.Compare):
        return False
    if len(node.test.ops) != 1 or len(node.test.comparators) != 1:
        return False
    left, right = node.test.left, node.test.comparators[0]
    return (
        isinstance(left, ast.Name) and left.id == "__name__" and isinstance(right, ast.Constant) and right.value == "__main__"
    ) or (
        isinstance(right, ast.Name) and right.id == "__name__" and isinstance(left, ast.Constant) and left.value == "__main__"
    )


def _source_imports(tree: ast.Module, module: str, is_package: bool, path: str) -> list[dict[str, Any]]:
    package = module if is_package else module.rpartition(".")[0]
    result: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                result.append({
                    "source": module, "path": path, "line": node.lineno, "kind": "import",
                    "imported": alias.name, "names": [], "base": alias.name,
                })
        elif isinstance(node, ast.ImportFrom):
            target_package = package
            if node.level:
                components = target_package.split(".") if target_package else []
                remove = node.level - 1
                target_package = ".".join(components[:len(components) - remove]) if remove and remove < len(components) else (target_package if remove == 0 else "")
            base = ".".join(part for part in (target_package, node.module or "") if part) if node.level else (node.module or "")
            names = [alias.name for alias in node.names]
            result.append({
                "source": module, "path": path, "line": node.lineno, "kind": "from",
                "imported": base or ".", "names": names, "base": base,
            })
    return sorted(result, key=lambda item: (item["line"], item["kind"], item["imported"]))


def _resolve(base: str, names: list[str], known: set[str]) -> str | None:
    candidates: list[str] = []
    if base:
        candidates.extend(f"{base}.{name}" for name in names if name and name != "*")
        candidates.append(base)
    for candidate in candidates:
        current = candidate
        while current:
            if current in known:
                return current
            if "." not in current:
                break
            current = current.rpartition(".")[0]
    return None


def _cycles(nodes: list[str], edges: list[dict[str, Any]]) -> list[list[str]]:
    adjacency = {node: set() for node in nodes}
    reverse = {node: set() for node in nodes}
    for edge in edges:
        source, target = edge["source"], edge["target"]
        if source in adjacency and target in adjacency:
            adjacency[source].add(target)
            reverse[target].add(source)
    visited: set[str] = set()
    finish: list[str] = []
    for start in sorted(nodes):
        if start in visited:
            continue
        stack: list[tuple[str, bool]] = [(start, False)]
        while stack:
            node, expanded = stack.pop()
            if expanded:
                finish.append(node)
                continue
            if node in visited:
                continue
            visited.add(node)
            stack.append((node, True))
            stack.extend((n, False) for n in sorted(adjacency[node], reverse=True) if n not in visited)
    visited.clear()
    groups: list[list[str]] = []
    for start in reversed(finish):
        if start in visited:
            continue
        component: list[str] = []
        stack = [start]
        visited.add(start)
        while stack:
            node = stack.pop()
            component.append(node)
            for neighbor in sorted(reverse[node], reverse=True):
                if neighbor not in visited:
                    visited.add(neighbor)
                    stack.append(neighbor)
        component.sort()
        if len(component) > 1 or (len(component) == 1 and component[0] in adjacency[component[0]]):
            groups.append(component)
    return sorted(groups, key=lambda group: (group[0], len(group)))


def scan_repository(
    repository: str | os.PathLike[str] = ".",
    *,
    excludes: Iterable[str] = (),
    max_files: int = MAX_FILE_COUNT,
    max_python_bytes: int = MAX_PYTHON_BYTES,
) -> dict[str, Any]:
    """Inspect a directory without importing or executing its Python modules."""
    raw = Path(repository).expanduser()
    try:
        root = raw.resolve(strict=True)
    except (OSError, RuntimeError, ValueError) as exc:
        raise RepoAtlasError(f"Repository path cannot be resolved: {raw!r}") from exc
    if not root.is_dir():
        raise RepoAtlasError(f"Repository path is not a directory: {root}")
    if max_files < 1 or max_python_bytes < 1:
        raise RepoAtlasError("Scan limits must be positive integers.")
    extra = tuple(excludes)
    root_rules = _load_ignore_file(root / ".gitignore", "") if (root / ".gitignore").is_file() else []
    rules_by_dir: dict[str, list[dict[str, Any]]] = {"": root_rules}
    files: list[dict[str, Any]] = []
    python_paths: list[tuple[str, Path, int]] = []
    warnings: list[dict[str, str]] = []
    total_bytes = 0

    def walk_error(error: OSError) -> None:
        warnings.append({"code": "DIRECTORY_READ_FAILED", "path": str(error.filename or "."), "message": str(error)[:250]})

    for current_text, dirs, names in os.walk(root, topdown=True, followlinks=False, onerror=walk_error):
        current = Path(current_text)
        current_rel = "" if current == root else _relative(current, root)
        rules = list(rules_by_dir.get(current_rel, []))
        ignore_file = current / ".gitignore"
        if current_rel and ignore_file.is_file():
            rules.extend(_load_ignore_file(ignore_file, current_rel))
        kept: list[str] = []
        for name in sorted(dirs):
            candidate = current / name
            relative = _relative(candidate, root)
            if candidate.is_symlink() or _ignored(relative, True, rules, extra):
                continue
            rules_by_dir[relative] = list(rules)
            kept.append(name)
        dirs[:] = kept
        for name in sorted(names):
            candidate = current / name
            relative = _relative(candidate, root)
            if candidate.is_symlink() or _ignored(relative, False, rules, extra):
                continue
            try:
                size = candidate.stat().st_size
            except OSError as exc:
                warnings.append({"code": "FILE_STAT_FAILED", "path": relative, "message": str(exc)[:250]})
                continue
            if size > MAX_SINGLE_FILE_BYTES:
                warnings.append({"code": "FILE_TOO_LARGE", "path": relative, "message": f"Skipped file above {MAX_SINGLE_FILE_BYTES} bytes."})
                continue
            if len(files) >= max_files:
                raise RepoAtlasError(f"Repository exceeds --max-files={max_files}. Narrow the scan with --exclude or raise the limit.")
            total_bytes += size
            files.append({"path": relative, "category": _category(relative), "extension": candidate.suffix.lower(), "size_bytes": size})
            if candidate.suffix.lower() == ".py":
                python_paths.append((relative, candidate, size))
    files.sort(key=lambda item: item["path"].casefold())

    modules: list[dict[str, Any]] = []
    raw_imports: list[dict[str, Any]] = []
    root_name = root.name or "repository"
    for relative, path, size in sorted(python_paths, key=lambda item: item[0]):
        module, is_package = _module_name(relative, root_name)
        source = ""
        tree = None
        if size > max_python_bytes:
            warnings.append({"code": "PYTHON_FILE_TOO_LARGE", "path": relative, "message": f"Skipped AST parsing above {max_python_bytes} bytes."})
        else:
            try:
                with tokenize.open(path) as handle:
                    source = handle.read(max_python_bytes + 1)
                if len(source.encode("utf-8", errors="replace")) <= max_python_bytes:
                    tree = ast.parse(source, filename=relative, type_comments=True)
                else:
                    warnings.append({"code": "PYTHON_FILE_TOO_LARGE", "path": relative, "message": f"Skipped AST parsing above {max_python_bytes} bytes."})
            except (OSError, UnicodeError, SyntaxError, ValueError) as exc:
                warnings.append({"code": "PYTHON_PARSE_FAILED", "path": relative, "message": str(exc)[:250]})
        if tree is None:
            modules.append({
                "name": module, "path": relative, "is_package": is_package,
                "line_count": len(source.splitlines()), "function_count": 0, "class_count": 0, "import_count": 0,
                "has_main_guard": False, "docstring": None, "syntax_error": True, "analysis_status": "partial",
            })
            continue
        imports = _source_imports(tree, module, is_package, relative)
        raw_imports.extend(imports)
        doc = ast.get_docstring(tree, clean=True)
        doc_summary = " ".join(doc.splitlines()).strip() if doc else None
        modules.append({
            "name": module, "path": relative, "is_package": is_package,
            "line_count": len(source.splitlines()),
            "function_count": sum(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) for node in ast.walk(tree)),
            "class_count": sum(isinstance(node, ast.ClassDef) for node in ast.walk(tree)),
            "import_count": len(imports),
            "has_main_guard": any(_main_guard(node) for node in ast.walk(tree)),
            "docstring": doc_summary[:220] + ("…" if doc_summary and len(doc_summary) > 220 else "") if doc_summary else None,
            "syntax_error": False, "analysis_status": "parsed",
        })
    modules.sort(key=lambda item: (item["name"], item["path"]))
    known = {module["name"] for module in modules}
    stdlib = getattr(sys, "stdlib_module_names", frozenset())
    external: set[str] = set()
    imports: list[dict[str, Any]] = []
    edge_map: dict[tuple[str, str], dict[str, Any]] = {}
    for raw_import in raw_imports:
        base = raw_import["base"]
        imported_names = raw_import["names"] if raw_import["kind"] == "from" else []
        candidates = [base]
        if raw_import["kind"] == "from":
            candidates = [f"{base}.{name}" for name in imported_names if name != "*"] + [base]
        resolved = None
        for candidate in candidates:
            resolved = _resolve(candidate, [], known)
            if resolved:
                break
        top_name = base.split(".", 1)[0] if base else ""
        if resolved:
            classification = "internal"
            key = (raw_import["source"], resolved)
            edge = edge_map.setdefault(key, {"source": key[0], "target": key[1], "count": 0, "lines": []})
            edge["count"] += 1
            edge["lines"].append(raw_import["line"])
        elif top_name and top_name in stdlib:
            classification = "stdlib"
        else:
            classification = "external" if top_name else "unresolved"
            if top_name:
                external.add(top_name)
        record = {key: value for key, value in raw_import.items() if key != "base"}
        record.update({"classification": classification, "resolved_module": resolved})
        imports.append(record)
    edges = sorted(edge_map.values(), key=lambda item: (item["source"], item["target"]))
    for edge in edges:
        edge["lines"] = sorted(set(edge["lines"]))
    if len(edges) > MAX_GRAPH_EDGES:
        raise RepoAtlasError(f"Graph exceeds {MAX_GRAPH_EDGES} unique edges; narrow the scan.")
    names = sorted(known)
    cycle_list = _cycles(names, edges)
    indegree = {name: 0 for name in names}
    outdegree = {name: 0 for name in names}
    for edge in edges:
        outdegree[edge["source"]] += 1
        indegree[edge["target"]] += 1
    for module in modules:
        module["in_degree"] = indegree.get(module["name"], 0)
        module["out_degree"] = outdegree.get(module["name"], 0)
    categories: dict[str, int] = defaultdict(int)
    for item in files:
        categories[item["category"]] += 1
    entries: list[dict[str, str]] = []
    for module in modules:
        if module["has_main_guard"]:
            entries.append({"path": module["path"], "kind": "main-guard", "module": module["name"]})
        if Path(module["path"]).name == "__main__.py":
            entries.append({"path": module["path"], "kind": "python-module-entry", "module": module["name"]})
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        try:
            import tomllib
            toml = tomllib.loads(pyproject.read_text(encoding="utf-8"))
            scripts = toml.get("project", {}).get("scripts", {})
            if isinstance(scripts, dict):
                for name, target in sorted(scripts.items()):
                    if isinstance(name, str) and isinstance(target, str):
                        entries.append({"path": "pyproject.toml", "kind": "console-script", "module": f"{name} -> {target}"})
        except ImportError:
            pass
        except (OSError, ValueError, TypeError):
            warnings.append({"code": "PYPROJECT_PARSE_FAILED", "path": "pyproject.toml", "message": "Unable to parse project script metadata."})
    entries.sort(key=lambda item: (item["path"], item["kind"], item["module"]))
    imports.sort(key=lambda item: (item["source"], item["line"], item["imported"]))
    warnings.sort(key=lambda item: (item["path"], item["code"], item["message"]))
    py_count = sum(item["extension"] == ".py" for item in files)
    total_lines = sum(item["line_count"] for item in modules)
    readmes = [item for item in files if Path(item["path"]).name.lower().startswith("readme")]
    findings: list[dict[str, Any]] = []
    if not readmes:
        findings.append({"code": "README_MISSING", "severity": "warning", "message": "No README was found in the included repository tree.", "recommendation": "Add the purpose, supported scope, installation, quick start, examples, and contribution instructions."})
    if not entries:
        findings.append({"code": "ENTRYPOINT_NOT_DETECTED", "severity": "info", "message": "No Python main guard, __main__.py, or detected console script was found.", "recommendation": "Document the intended invocation or define an explicit package entry point if the project is executable."})
    if cycle_list:
        findings.append({"code": "IMPORT_CYCLES_DETECTED", "severity": "warning", "message": f"{len(cycle_list)} strongly connected import component(s) were detected.", "recommendation": "Review cyclic dependencies and consider extracting shared interfaces into lower-level modules."})
    parse_count = sum(bool(module["syntax_error"]) for module in modules)
    if parse_count:
        findings.append({"code": "PYTHON_PARSE_ERRORS", "severity": "warning", "message": f"{parse_count} Python file(s) could not be fully parsed.", "recommendation": "Inspect parse warnings; metrics and dependency edges for those files are incomplete."})
    if not modules:
        findings.append({"code": "NO_PYTHON_MODULES", "severity": "info", "message": "No Python files were included; only the generic file inventory is available.", "recommendation": "This version analyzes Python ASTs. Add Python files to enable module relationship analysis."})
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": {"name": "repoatlas", "version": __version__},
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "repository": {"name": root.name, "root_label": ".", "absolute_path_recorded": False},
        "summary": {
            "file_count": len(files), "python_file_count": py_count, "documentation_file_count": categories["documentation"],
            "configuration_file_count": categories["configuration"], "test_file_count": categories["test"],
            "total_bytes": total_bytes, "python_line_count": total_lines, "module_count": len(modules),
            "parsed_module_count": sum(module["analysis_status"] == "parsed" for module in modules),
            "import_record_count": len(imports), "internal_edge_count": len(edges), "external_import_count": len(external),
            "cycle_count": len(cycle_list), "parse_warning_count": parse_count, "entrypoint_count": len(entries),
            "finding_count": len(findings),
        },
        "files": files, "modules": modules, "imports": imports, "edges": edges,
        "external_imports": sorted(external), "cycles": cycle_list, "entrypoints": entries, "findings": findings,
        "warnings": warnings,
        "analysis": {
            "language": "Python", "method": "ast", "project_code_executed": False, "network_requests_made": False,
            "absolute_paths_recorded": False, "max_python_bytes": max_python_bytes, "max_files": max_files,
            "limitations": [
                "Static import edges show declared imports, not runtime call paths.",
                "Dynamic imports, reflection, plugin discovery, and generated modules may not be resolved.",
                "External imports are not proof that a package is installed or available at runtime.",
                "Nested ignore files use a practical subset of Git ignore semantics.",
            ],
        },
    }


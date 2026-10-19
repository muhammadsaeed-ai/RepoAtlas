"""RepoAtlas command-line interface."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from repoatlas import __version__
from repoatlas.core import RepoAtlasError, scan_repository
from repoatlas.render import render_output, validate_atlas


def _atomic_write(filename: str, content: str, *, force: bool = False) -> Path:
    target = Path(filename).expanduser().absolute()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise RepoAtlasError(f"Cannot create output directory {target.parent}: {exc}") from exc
    if target.exists() and not force:
        raise RepoAtlasError(f"Output already exists: {target}. Use --force only when replacement is intended.")
    descriptor = None
    temporary = None
    try:
        descriptor, temp_name = tempfile.mkstemp(prefix=f".{target.name}.repoatlas-", suffix=".tmp", dir=target.parent)
        temporary = Path(temp_name)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            descriptor = None
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if force:
            os.replace(temporary, target)
        else:
            try:
                os.link(temporary, target)
            except FileExistsError as exc:
                raise RepoAtlasError(
                    f"Output already exists: {target}. Use --force only when replacement is intended."
                ) from exc
            temporary.unlink()
        return target
    except RepoAtlasError:
        raise
    except (OSError, ValueError) as exc:
        raise RepoAtlasError(f"Could not write output to {target}: {exc}") from exc
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="repoatlas",
        description="Map a Python repository into inventory, import graphs, cycle diagnostics, and visual exports.",
        epilog="Static analysis only: RepoAtlas never imports or executes target project modules.",
    )
    parser.add_argument("--version", action="version", version=f"RepoAtlas {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    scan = sub.add_parser("scan", help="Scan a repository and write a versioned JSON atlas.")
    scan.add_argument("repository", nargs="?", default=".", help="Repository directory; defaults to current directory.")
    scan.add_argument("-o", "--output", default="repoatlas.json", help="JSON snapshot path, or '-' for stdout.")
    scan.add_argument("--exclude", action="append", default=[], help="Additional exclusion glob; repeatable.")
    scan.add_argument("--max-files", type=int, default=50_000, help="Maximum inventoried files.")
    scan.add_argument(
        "--max-python-bytes", type=int, default=2 * 1024 * 1024, help="Maximum Python bytes parsed per file."
    )
    scan.add_argument("--force", action="store_true", help="Replace output when it exists.")
    render = sub.add_parser("render", help="Render a snapshot as Markdown, Mermaid, SVG, or JSON.")
    render.add_argument("snapshot", help="Path to a RepoAtlas JSON snapshot.")
    render.add_argument("--format", choices=("markdown", "mermaid", "svg", "json"), default="markdown")
    render.add_argument("-o", "--output", help="Output path; stdout is used by default.")
    render.add_argument("--force", action="store_true", help="Replace output when it exists.")
    return parser


def _load_snapshot(filename: str) -> dict[str, Any]:
    source = Path(filename).expanduser()
    try:
        with source.open("rb") as handle:
            raw = handle.read(64 * 1024 * 1024 + 1)
        if len(raw) > 64 * 1024 * 1024:
            raise RepoAtlasError("Snapshot exceeds 64 MiB; refusing to load an unbounded file.")
        data = json.loads(raw.decode("utf-8"))
    except RepoAtlasError:
        raise
    except FileNotFoundError as exc:
        raise RepoAtlasError(f"Snapshot not found: {source}") from exc
    except (OSError, UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise RepoAtlasError(f"Cannot read a valid JSON snapshot from {source}: {exc}") from exc
    return validate_atlas(data)


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    try:
        if args.command == "scan":
            root = Path(args.repository).expanduser().resolve(strict=True)
            excludes = list(args.exclude)
            if args.output != "-":
                try:
                    output_path = Path(args.output).expanduser().resolve(strict=False).relative_to(root).as_posix()
                    excludes.append(output_path)
                except (OSError, ValueError):
                    pass
            atlas = scan_repository(
                root, excludes=excludes, max_files=args.max_files, max_python_bytes=args.max_python_bytes
            )
            serialized = json.dumps(atlas, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
            if args.output == "-":
                sys.stdout.write(serialized)
            else:
                target = _atomic_write(args.output, serialized, force=args.force)
                summary = atlas["summary"]
                print(f"RepoAtlas scan complete: {atlas['repository']['name']}")
                print(
                    f"Files: {summary['file_count']:,} | Python modules: {summary['module_count']:,} | Internal edges: {summary['internal_edge_count']:,} | Cycles: {summary['cycle_count']:,}"
                )
                print(f"Snapshot: {target}")
                if atlas["warnings"]:
                    print(f"Warnings: {len(atlas['warnings'])}. Render Markdown for details.")
                print("Static analysis only: project code was not executed; no network requests were made.")
            return 0
        if args.command == "render":
            atlas = _load_snapshot(args.snapshot)
            result = render_output(atlas, args.format)
            if args.output is None or args.output == "-":
                sys.stdout.write(result)
            else:
                target = _atomic_write(args.output, result, force=args.force)
                print(f"Rendered {args.format}: {target}")
            return 0
        parser.error(f"Unknown command: {args.command}")
        return 2
    except RepoAtlasError as exc:
        print(f"repoatlas: error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("repoatlas: interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())

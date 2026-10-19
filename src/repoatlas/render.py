"""Render RepoAtlas snapshots as Markdown, Mermaid, JSON, or standalone SVG."""

from __future__ import annotations

import html
import json
import math
from typing import Any

from repoatlas import SCHEMA_VERSION
from repoatlas.errors import RepoAtlasError


def validate_atlas(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise RepoAtlasError("Atlas snapshot must be a JSON object.")
    if type(data.get("schema_version")) is not int or data.get("schema_version") != SCHEMA_VERSION:
        raise RepoAtlasError(f"Unsupported atlas schema version: {data.get('schema_version')!r}.")
    for key in ("repository", "summary", "analysis"):
        if not isinstance(data.get(key), dict):
            raise RepoAtlasError(f"Invalid atlas snapshot: {key} must be an object.")
    for key in ("files", "modules", "imports", "edges", "cycles", "entrypoints", "findings", "warnings"):
        if not isinstance(data.get(key), list):
            raise RepoAtlasError(f"Invalid atlas snapshot: {key} must be a list.")
    for index, module in enumerate(data["modules"]):
        if (
            not isinstance(module, dict)
            or not isinstance(module.get("name"), str)
            or not isinstance(module.get("path"), str)
        ):
            raise RepoAtlasError(f"Invalid snapshot module at index {index}.")
    for index, edge in enumerate(data["edges"]):
        if (
            not isinstance(edge, dict)
            or not isinstance(edge.get("source"), str)
            or not isinstance(edge.get("target"), str)
        ):
            raise RepoAtlasError(f"Invalid snapshot edge at index {index}.")
    return data


def render_json(atlas: dict[str, Any]) -> str:
    validate_atlas(atlas)
    return json.dumps(atlas, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def render_mermaid(atlas: dict[str, Any], *, max_nodes: int = 120) -> str:
    validate_atlas(atlas)
    modules = sorted(atlas["modules"], key=lambda item: item["name"])
    chosen = modules[:max_nodes]
    identifiers = {item["name"]: f"m{index}" for index, item in enumerate(chosen)}
    lines = ["flowchart LR", "  %% RepoAtlas renders declared static imports; these are not runtime traces."]
    for module in chosen:
        label = module["name"].replace('"', "'").replace("\n", " ")
        path = module["path"].replace('"', "'").replace("\n", " ")
        lines.append(f'  {identifiers[module["name"]]}["{label}<br/>{path}"]')
    count = 0
    for edge in sorted(atlas["edges"], key=lambda item: (item["source"], item["target"])):
        if edge["source"] in identifiers and edge["target"] in identifiers:
            lines.append(f"  {identifiers[edge['source']]} --> {identifiers[edge['target']]}")
            count += 1
    if len(modules) > len(chosen):
        lines.append(f"  %% Graph limited to {len(chosen)} of {len(modules)} modules.")
    if not count:
        lines.append('  empty["No internal imports detected"]')
    lines.extend(
        [
            "",
            "classDef source fill:#102846,stroke:#37DFF8,color:#EAF7FF;",
            "classDef test fill:#1C1B3D,stroke:#A78BFA,color:#F3EFFF;",
            "classDef issue fill:#3C1B2A,stroke:#FF839A,color:#FFF0F2;",
        ]
    )
    for module in chosen:
        name = module["name"]
        style = (
            "issue"
            if module.get("syntax_error")
            else ("test" if module["path"].startswith("tests/") or "/tests/" in module["path"] else "source")
        )
        lines.append(f"  class {identifiers[name]} {style};")
    return "\n".join(lines) + "\n"


def render_svg(atlas: dict[str, Any], *, max_nodes: int = 48, max_edges: int = 160) -> str:
    """Render an accessible, static dependency graph with no external assets or JavaScript."""
    validate_atlas(atlas)
    modules = sorted(atlas["modules"], key=lambda item: item["name"])[:max_nodes]
    card_w, card_h, gap_x, gap_y, columns = 252, 68, 30, 24, 4
    rows = max(1, math.ceil(len(modules) / columns))
    height = 112 + rows * (card_h + gap_y) + 54
    positions: dict[str, tuple[int, int]] = {}
    for index, module in enumerate(modules):
        positions[module["name"]] = (
            24 + (index % columns) * (card_w + gap_x),
            87 + (index // columns) * (card_h + gap_y),
        )
    edges = [
        edge
        for edge in sorted(atlas["edges"], key=lambda item: (item["source"], item["target"]))
        if edge["source"] in positions and edge["target"] in positions
    ][:max_edges]
    repo = html.escape(str(atlas["repository"].get("name", "repository")))
    output = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="{height}" viewBox="0 0 1200 {height}" role="img" aria-labelledby="title desc">',
        f'<title id="title">RepoAtlas dependency map — {repo}</title>',
        '<desc id="desc">Static Python import graph. Nodes are Python modules; arrows are declared internal import relationships. Graph rendering is bounded for readability.</desc>',
        '<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#07111F"/><stop offset="1" stop-color="#10172E"/></linearGradient><linearGradient id="accent" x1="0" y1="0" x2="1" y2="0"><stop stop-color="#24DFF8"/><stop offset="1" stop-color="#827CFF"/></linearGradient><marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L0,6 L6,3 z" fill="#4DA5D7"/></marker></defs>',
        f'<rect width="1200" height="{height}" rx="22" fill="url(#bg)" stroke="#1E4267"/>',
        f'<text x="28" y="35" fill="#F0F7FF" font-family="Inter,Segoe UI,Arial,sans-serif" font-size="22" font-weight="750">{repo}</text>',
        '<text x="28" y="58" fill="#84ABCF" font-family="Inter,Segoe UI,Arial,sans-serif" font-size="12">REPOATLAS · STATIC PYTHON DEPENDENCY MAP</text>',
        f'<text x="1170" y="35" text-anchor="end" fill="#75DFFF" font-family="Inter,Segoe UI,Arial,sans-serif" font-size="12">{len(atlas["modules"])} modules · {len(atlas["edges"])} edges · {len(atlas["cycles"])} cycles</text>',
    ]
    for edge in edges:
        x1, y1 = positions[edge["source"]]
        x2, y2 = positions[edge["target"]]
        cx1, cy1 = x1 + card_w / 2, y1 + card_h / 2
        cx2, cy2 = x2 + card_w / 2, y2 + card_h / 2
        if edge["source"] == edge["target"]:
            output.append(
                f'<path d="M{cx1 + 48:.1f} {cy1 - 12:.1f} C{cx1 + 90:.1f} {cy1 - 54:.1f} {cx1 - 24:.1f} {cy1 - 54:.1f} {cx1 - 48:.1f} {cy1 - 12:.1f}" fill="none" stroke="#E39A73" stroke-width="1.5" marker-end="url(#arrow)"/>'
            )
        else:
            output.append(
                f'<path d="M{cx1:.1f} {cy1:.1f} L{cx2:.1f} {cy2:.1f}" fill="none" stroke="#4DA5D7" stroke-width="1.4" marker-end="url(#arrow)" opacity=".55"/>'
            )
    for module in modules:
        x, y = positions[module["name"]]
        if module.get("syntax_error"):
            stroke, dot = "#FF839A", "#FF839A"
        elif module["path"].startswith("tests/") or "/tests/" in module["path"]:
            stroke, dot = "#A78BFA", "#BBA8FF"
        else:
            stroke, dot = "#2A6F98", "#3CE0FA"
        label = module["name"] if len(module["name"]) <= 30 else module["name"][:27] + "…"
        path = module["path"] if len(module["path"]) <= 36 else module["path"][:33] + "…"
        output.extend(
            [
                f'<rect x="{x}" y="{y}" width="{card_w}" height="{card_h}" rx="11" fill="#0B1D32" stroke="{stroke}" stroke-width="1.4"/>',
                f'<circle cx="{x + 17}" cy="{y + 20}" r="4.5" fill="{dot}"/>',
                f'<text x="{x + 29}" y="{y + 24}" fill="#F0F7FF" font-family="ui-monospace,Consolas,monospace" font-size="12" font-weight="700">{html.escape(label)}</text>',
                f'<text x="{x + 14}" y="{y + 47}" fill="#91B1CE" font-family="Inter,Segoe UI,Arial,sans-serif" font-size="10">{html.escape(path)}</text>',
            ]
        )
    footer = height - 29
    message = f"Showing {len(modules)} of {len(atlas['modules'])} modules and {len(edges)} of {len(atlas['edges'])} edges. Static imports are not runtime traces."
    output.append(
        f'<text x="28" y="{footer}" fill="#7898BA" font-family="Inter,Segoe UI,Arial,sans-serif" font-size="11">{html.escape(message)}</text>'
    )
    output.append("</svg>")
    return "\n".join(output) + "\n"


def render_markdown(atlas: dict[str, Any], *, max_files: int = 80, max_modules: int = 80) -> str:
    validate_atlas(atlas)
    repo, summary = atlas["repository"].get("name", "repository"), atlas["summary"]
    modules = sorted(atlas["modules"], key=lambda item: (-item.get("out_degree", 0), item["name"]))
    files = sorted(atlas["files"], key=lambda item: item["path"])
    lines = [
        f"# RepoAtlas report — {repo}",
        "",
        "> Generated from static source inspection. Declared imports are not proof of runtime execution.",
        "",
        "## At a glance",
        "",
        "| Metric | Result |",
        "|---|---:|",
        f"| Files inventoried | {summary.get('file_count', 0)} |",
        f"| Python files | {summary.get('python_file_count', 0)} |",
        f"| Python lines | {summary.get('python_line_count', 0)} |",
        f"| Parsed modules | {summary.get('parsed_module_count', 0)} / {summary.get('module_count', 0)} |",
        f"| Internal dependency edges | {summary.get('internal_edge_count', 0)} |",
        f"| External import roots | {summary.get('external_import_count', 0)} |",
        f"| Import cycles | {summary.get('cycle_count', 0)} |",
        f"| Entry-point signals | {summary.get('entrypoint_count', 0)} |",
        f"| Structural findings | {summary.get('finding_count', 0)} |",
        "",
        "## Structural findings",
        "",
    ]
    if atlas["findings"]:
        for finding in atlas["findings"]:
            lines.append(f"- **[{finding.get('severity', 'info').upper()}] {finding['code']}** — {finding['message']}")
            lines.append(f"  - Suggested action: {finding.get('recommendation', 'Review this signal.')}")
    else:
        lines.append("No repository-level findings were triggered by the current rule set.")
    lines.extend(["", "## High-connectivity modules", ""])
    if modules:
        lines.extend(["| Module | Outgoing | Incoming | Functions | Classes | Path |", "|---|---:|---:|---:|---:|---|"])
        for item in modules[:max_modules]:
            path = item["path"].replace("|", "\\\\|")
            name = item["name"].replace("|", "\\\\|")
            lines.append(
                f"| {name} | {item.get('out_degree', 0)} | {item.get('in_degree', 0)} | {item.get('function_count', 0)} | {item.get('class_count', 0)} | {path} |"
            )
        if len(modules) > max_modules:
            lines.append(f"\n*Showing {max_modules} of {len(modules)} modules.*")
    else:
        lines.append("No Python modules found.")
    lines.extend(["", "## Import cycles", ""])
    if atlas["cycles"]:
        for index, cycle in enumerate(atlas["cycles"], 1):
            lines.append(f"{index}. " + " → ".join(cycle) + f" → {cycle[0]}")
    else:
        lines.append("No strongly connected import components were detected.")
    lines.extend(["", "## Entrypoints", ""])
    if atlas["entrypoints"]:
        lines.extend(["| Type | Command / module | Path |", "|---|---|---|"])
        for item in atlas["entrypoints"]:
            lines.append(f"| {item['kind']} | {item['module']} | {item['path']} |")
    else:
        lines.append("No Python entry-point signal was found.")
    lines.extend(["", "## External import roots", ""])
    lines.append(", ".join(atlas["external_imports"]) if atlas["external_imports"] else "None recorded.")
    lines.extend(["", "## File inventory", ""])
    if files:
        lines.extend(["| Path | Category | Bytes |", "|---|---|---:|"])
        for item in files[:max_files]:
            file_path = item["path"].replace("|", "\\\\|")
            lines.append(f"| {file_path} | {item['category']} | {item['size_bytes']} |")
        if len(files) > max_files:
            lines.append(
                f"\n*Showing {max_files} of {len(files)} files. The JSON snapshot contains the complete inventory.*"
            )
    else:
        lines.append("No files were inventoried.")
    if atlas["warnings"]:
        lines.extend(["", "## Warnings", ""])
        for item in atlas["warnings"][:100]:
            lines.append(f"- **{item['code']}** — {item['path']}: {item['message']}")
        if len(atlas["warnings"]) > 100:
            lines.append(f"- {len(atlas['warnings']) - 100} additional warnings omitted.")
    lines.extend(
        [
            "",
            "## Interpretation and limits",
            "",
            "- Python is parsed with the standard-library AST module; target code is not imported or executed.",
            "- Static dependency edges represent declared imports, not runtime calls.",
            "- Dynamic imports, reflection, plugin discovery and generated modules may be absent.",
            "- An external import root is not proof that the dependency is installed or available.",
            "- Paths are repository-relative, but module names, docstrings and paths may reveal private structure. Review before sharing.",
            "",
            f"_RepoAtlas {atlas['tool']['version']} · Snapshot schema {atlas['schema_version']} · {atlas['generated_at']}_",
            "",
        ]
    )
    return "\n".join(lines)


def render_output(atlas: dict[str, Any], fmt: str) -> str:
    if fmt == "json":
        return render_json(atlas)
    if fmt == "markdown":
        return render_markdown(atlas)
    if fmt == "mermaid":
        return render_mermaid(atlas)
    if fmt == "svg":
        return render_svg(atlas)
    raise RepoAtlasError(f"Unsupported format: {fmt}")

# Usage guide

## Install from a clone

~~~bash
git clone https://github.com/muhammadsaeed-ai/RepoAtlas.git
cd RepoAtlas
python -m venv .venv
~~~

Activate the environment and install:

~~~bash
python -m pip install .
repoatlas --help
~~~

For development:

~~~bash
python -m pip install -e ".[dev]"
python -m pytest
~~~

## Scan and export

~~~bash
repoatlas scan /path/to/project --output atlas.json

# Opt in to adding module-level docstring summaries to the snapshot
repoatlas scan /path/to/project --include-docstrings --output atlas-with-docstrings.json
repoatlas render atlas.json --format markdown --output atlas-report.md
repoatlas render atlas.json --format mermaid --output dependency-graph.mmd
repoatlas render atlas.json --format svg --output dependency-map.svg
~~~

Use --force only when an existing output should be replaced. Snapshot files can be rendered multiple times without scanning source again.

## Scope and interpretation

- A module node represents an inventoried Python source file.
- A directed edge represents a declared import resolved to an included project module.
- A cycle is a strongly connected component of mutually connected imports.
- In-degree counts distinct modules importing this module; out-degree counts distinct target modules this module imports.
- An external import root was not resolved to the repository or standard-library name set. This does not prove the package is installed or available at runtime.
- Files and source AST reads have limits. Common generated directories are excluded, and .gitignore patterns are honored using a practical subset of Git's behavior.

## Questions

### Does RepoAtlas execute repository code?

No. It parses Python source with ast and never imports the target modules.

### Does it upload source?

No. The scanner makes no network requests. Module docstring summaries are excluded by default; if you enable --include-docstrings, those summaries are added to the snapshot. Review reports before sharing because paths and dependency names may expose private structure.

### Does it support JavaScript, Go or Rust?

Not in v0.1.0. These files appear in the generic inventory, but dependency analysis is Python-only.

### Why can imports be missing?

Dynamic imports, reflection, plugin registrations, import-time mutations and generated modules are not generally discoverable from static syntax. Treat results as navigational evidence, then validate important conclusions.

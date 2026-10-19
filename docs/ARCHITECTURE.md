# RepoAtlas architecture

RepoAtlas v0.1.0 separates filesystem traversal, Python AST parsing, graph construction, diagnostics, serialization and rendering.

~~~mermaid
flowchart TD
  A[Repository root] --> B[Ignore-aware traversal]
  B --> C[Relative file inventory]
  B --> D[Bounded Python source reads]
  D --> E[AST parser]
  E --> F[Modules and import records]
  F --> G[Internal dependency graph]
  G --> H[Cycle and connectivity analysis]
  C --> I[Versioned atlas JSON]
  H --> I
  I --> J[Markdown report]
  I --> K[Mermaid diagram]
  I --> L[Standalone SVG map]
~~~

## Components

- core.py: ignore-aware traversal, source limits, AST metrics, import classification, internal dependency resolution, SCC detection and structural findings.
- render.py: schema validation plus JSON, Markdown, Mermaid and SVG renderers.
- cli.py: argument handling, bounded snapshot loading, no-clobber output and error codes.
- tests: small temporary fixture repositories; tests do not depend on the project's own checkout.

## Data model

Each parsed Python source becomes a module record with name, repository-relative path, package marker, line/function/class counts, optional docstring summary, main-guard signal and graph degree. Docstring summaries are omitted unless --include-docstrings is explicitly supplied. Each import declaration retains module, source path and line, import kind, imported symbol names, classification and resolved target when one is found.

Edges aggregate source/target relationships and keep source-line references. Cycles are strongly connected import components, calculated by iterative Kosaraju traversal rather than recursive DFS.

## Safety properties

1. Target code is never imported or executed.
2. Only Python source within a configurable byte limit is read for AST parsing.
3. Symlinks are skipped rather than followed.
4. Common virtualenv, vendor, cache and build directories are excluded by default.
5. Snapshots store relative paths, not the absolute repository root.
6. Module docstring summaries are excluded by default; users must explicitly opt in to serialize them.
6. File inventory, snapshot loading, and graph output are bounded.
7. SVG text is escaped; Mermaid identifiers are generated from a counter rather than copied from paths.
8. Scan and render do not make network requests.

## Known limitations

- Python syntax only in v0.1.0; other languages are inventoried but not parsed.
- Static edges represent declared imports, not runtime call paths. Dynamic imports, plugin discovery, reflection and generated modules can be missed.
- Duplicate module names and unusual namespace-package layouts can make resolution ambiguous.
- Nested ignore support is a practical subset of the full Git pattern semantics.
- Console script metadata is parsed through tomllib on Python 3.11+; Python 3.10 still gets main guards and __main__.py detection.
- Findings are review prompts, not a quality score or proof of an architectural defect.
- SVG output is intentionally bounded for readability.

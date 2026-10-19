# Contributing to RepoAtlas

Thanks for helping make codebases easier to understand.

## Development

~~~bash
python -m venv .venv
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check src tests examples
python -m ruff format --check src tests examples
~~~

## Engineering requirements

- Add fixture-based tests for normal, edge, malformed-input, and cross-platform cases.
- Keep scanning static: never import or execute target-repository modules.
- Store relative paths; do not add absolute local paths without explicit review.
- Bound file traversal, source reads, snapshot reads, and graph exports.
- Keep reports deterministic and escape untrusted text in SVG/Mermaid output.
- Clearly label heuristics. Static import edges are not runtime traces.
- Do not add telemetry, source uploads, or network calls to the scanner.
- Update README, CHANGELOG, and docs for user-facing behavior.

Never submit private source code, credentials, or unreviewed repository dumps in public issues.

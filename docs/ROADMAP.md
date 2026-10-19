# Roadmap

## v0.1 — Python static atlas

- [x] Local file inventory and common generated-directory exclusions.
- [x] Practical root/nested ignore handling and explicit exclusion patterns.
- [x] AST metrics, import records, internal graph edges, and cycle detection.
- [x] Entry-point signals and basic structural findings.
- [x] JSON, Markdown, Mermaid and SVG export.
- [x] CLI input validation, output no-clobber policy, fixture tests and CI.

## v0.2 — Graph exploration

- [ ] Package filters, depth limits, focus modules, and edge-label options.
- [ ] Improve .gitignore semantics and test against Git where available.
- [ ] Detect duplicate module names and probable import shadowing.
- [ ] Additional SVG layouts and label density controls.
- [ ] Measure scan time and memory on a documented set of representative projects.

## v0.3 — Repository health

- [ ] Optional TODO/FIXME inventory and documentation coverage policies.
- [ ] Stable finding schema and configurable severity thresholds.
- [ ] Consistent console-entry-point detection across Python 3.10+.
- [ ] Interactive graph viewer backed by the same JSON graph model.

## Future language adapters

JavaScript/TypeScript, Go, Rust, and Java remain proposals. Each adapter should have parser-specific fixtures, confidence labels, ignore-aware source selection and documented accuracy boundaries.

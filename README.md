# RepoAtlas

<p align="center">
  <img src="assets/readme/progress-loop.gif" alt="Animated workflow indicator" width="420" />
</p>

<p align="center"><strong>Turn an unfamiliar codebase into a visual map of files, modules, imports, and architecture.</strong></p>
<p align="center">
  <a href="#the-idea">The idea</a> · <a href="#visual-workflow">Workflow</a> · <a href="#proposed-architecture">Architecture</a> · <a href="#roadmap">Roadmap</a>
</p>
<p align="center">
  <img alt="Stage: design proposal" src="https://img.shields.io/badge/stage-design%20proposal-7867FF?style=flat-square" />
  <img alt="Analysis approach" src="https://img.shields.io/badge/approach-local%20static%20analysis-2563EB?style=flat-square" />
  <img alt="Open source concept" src="https://img.shields.io/badge/project-open%20source%20concept-168AAD?style=flat-square" />
</p>

> **Project status: design-stage.** This repository currently contains the concept README only. There is no scanner, parser, graph engine, or CLI implementation available yet. The diagrams below illustrate the proposed design.

## The idea

RepoAtlas is a proposed **codebase analyzer and architecture visualization tool**. It should help a developer understand a new repository by generating a navigable inventory of files, modules, imports, dependencies, entry points, and architectural relationships.

The intended workflow is local-first: inspect source files that the user explicitly selects, build an inspectable relationship graph, then export documentation that a maintainer can review and commit.

## Visual workflow

<p align="center"><img src="assets/readme/workflow.svg" alt="Proposed RepoAtlas workflow from scanning a repository through import resolution and graph construction to Mermaid, SVG, and Markdown exports." width="100%" /></p>

## Proposed architecture

<p align="center"><img src="assets/readme/architecture.svg" alt="Proposed RepoAtlas architecture: repository scanner, language parsers, graph model, and visual documentation exporters." width="100%" /></p>

## What it aims to map

| Map layer | Examples | Intended output |
|---|---|---|
| Repository inventory | Source files, tests, configs, docs, generated folders | Filterable file tree and summary |
| Module relationships | Python imports and package boundaries | Directed dependency graph |
| Entry points | CLI commands, `__main__`, registered scripts | Entry-point index |
| Architectural clusters | Internal modules that reference each other | Candidate subsystem groups, labeled as heuristics |
| Documentation gaps | Modules or packages with no nearby docs | Optional checklist, not an automatic quality score |
| Exported diagrams | Module graphs and component relationships | SVG, Mermaid, Markdown, and JSON graph data |

Parser coverage, language support, and the accuracy of architectural clustering must be measured during implementation. RepoAtlas should not claim to understand arbitrary code or infer architecture perfectly from filenames alone.

## Intended outputs

- **Markdown reports** that introduce a repository and link to useful areas.
- **Mermaid diagrams** that can be edited in pull requests.
- **SVG architecture maps** suitable for README documentation.
- **Machine-readable graph data** for custom scripts or later visual tools.

These exports are planned and are not available as working commands yet.

## Design principles

- **Local-first analysis:** no source upload or telemetry by default.
- **Ignore-aware traversal:** respect version-control ignore rules and common virtualenv/build directories.
- **Bounded and deterministic:** stable ordering, sensible file-size limits, and reproducible output.
- **Explicit confidence:** distinguish parser-backed links from guessed clusters.
- **Reviewable changes:** generated README content should be opt-in and never silently overwrite hand-written documentation.

## Roadmap

- [ ] Define a versioned file/module graph schema.
- [ ] Implement safe repository traversal and ignore handling.
- [ ] Add Python AST import extraction and deterministic test fixtures.
- [ ] Build dependency graph algorithms and report output.
- [ ] Generate editable Mermaid and static SVG diagrams.
- [ ] Add CLI export options, size limits, and overwrite safeguards.
- [ ] Evaluate additional languages only after the Python workflow is reliable.

## Contributing

Useful early work includes schema design, parser test fixtures, edge-case repositories, and decisions about how to display large dependency graphs. Feature claims should be added to this README only after the relevant behavior is implemented and tested.

## Search and GitHub topics

Suggested topics: `codebase-analysis`, `architecture-visualization`, `dependency-graph`, `static-analysis`, `python`, `code-documentation`, `mermaid`, `repository-map`, `developer-tools`, `open-source`.

These keywords describe the planned project; search rankings or traffic are not guaranteed.

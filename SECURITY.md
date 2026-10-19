# Security policy

RepoAtlas is designed to analyze repositories locally. Its Python analyzer uses the AST parser and does not import or execute target modules. It reads file metadata, applicable ignore files, and Python source within a configurable size limit. The scanner does not upload source or call a remote API.

Generated reports may disclose relative file paths, module names, dependency names, and structural relationships. Module docstring summaries are excluded by default; if you pass --include-docstrings, those summaries can disclose additional repository details. Review output before sharing externally.

Report possible path traversal, unintended file reads, unbounded resource use, unsafe SVG/Mermaid output, or unintended code execution privately through GitHub's vulnerability reporting feature if enabled. Otherwise, contact the maintainer through an available private GitHub contact route. Do not post confidential repository contents in public issues.

Security fixes target the latest version; this early project is not independently penetration-tested or formally security-certified.

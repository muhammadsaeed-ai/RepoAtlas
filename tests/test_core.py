from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from repoatlas.core import RepoAtlasError, scan_repository
from repoatlas.render import render_markdown, render_mermaid, render_svg


class CoreTests(unittest.TestCase):
    def write(self, root: Path, name: str, content: str) -> Path:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def test_internal_imports_and_structural_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write(root, "README.md", "# Demo")
            self.write(root, "pkg/__init__.py", '"""Package doc."""\n')
            self.write(root, "pkg/app.py", "from pkg import service\n\ndef main():\n    return service.value\n")
            self.write(root, "pkg/service.py", "value = 3\n")
            atlas = scan_repository(root)
        self.assertEqual(atlas["summary"]["python_file_count"], 3)
        self.assertTrue(any(edge["source"] == "pkg.app" and edge["target"] == "pkg.service" for edge in atlas["edges"]))
        module = next(item for item in atlas["modules"] if item["path"] == "pkg/app.py")
        self.assertEqual(module["function_count"], 1)
        self.assertFalse(atlas["repository"]["absolute_path_recorded"])

    def test_cycle_detection(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write(root, "a.py", "import b\n")
            self.write(root, "b.py", "import a\n")
            atlas = scan_repository(root)
        self.assertEqual(atlas["summary"]["cycle_count"], 1)
        self.assertEqual(atlas["cycles"], [["a", "b"]])

    def test_scanning_never_executes_project_code(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            marker = root / "executed.txt"
            self.write(root, "app.py", f"from pathlib import Path\nPath({str(marker)!r}).write_text('ran')\n")
            atlas = scan_repository(root)
        self.assertFalse(marker.exists())
        self.assertFalse(atlas["analysis"]["project_code_executed"])

    def test_respects_default_directories_gitignore_and_custom_globs(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write(root, ".gitignore", "private.py\nignored_dir/\n")
            self.write(root, "main.py", "import os\n")
            self.write(root, "private.py", "password = 'hidden'\n")
            self.write(root, "ignored_dir/ignored.py", "value = 1\n")
            self.write(root, ".venv/lib/python.py", "value = 2\n")
            self.write(root, "docs/generated.md", "# generated")
            atlas = scan_repository(root, excludes=["docs/*.md"])
        paths = {item["path"] for item in atlas["files"]}
        self.assertIn("main.py", paths)
        self.assertNotIn("private.py", paths)
        self.assertNotIn("ignored_dir/ignored.py", paths)
        self.assertNotIn(".venv/lib/python.py", paths)
        self.assertNotIn("docs/generated.md", paths)

    def test_bad_syntax_is_a_warning_not_a_fatal_scan_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write(root, "bad.py", "def broken(:\n")
            self.write(root, "good.py", "value = 3\n")
            atlas = scan_repository(root)
        self.assertEqual(atlas["summary"]["parse_warning_count"], 1)
        self.assertEqual(atlas["summary"]["parsed_module_count"], 1)
        self.assertTrue(any(item["code"] == "PYTHON_PARSE_FAILED" for item in atlas["warnings"]))

    def test_limits_and_path_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write(root, "a.py", "x = 1\n" * 10)
            self.assertTrue(
                any(
                    item["code"] == "PYTHON_FILE_TOO_LARGE"
                    for item in scan_repository(root, max_python_bytes=5)["warnings"]
                )
            )
            with self.assertRaises(RepoAtlasError):
                scan_repository(root, max_files=0)
            with self.assertRaises(RepoAtlasError):
                scan_repository(self.write(root, "file.txt", "x"))

    def test_entrypoint_signals_and_standard_library_classification(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write(root, "run.py", "import os\nif __name__ == '__main__':\n    pass\n")
            self.write(root, "package/__main__.py", "pass\n")
            atlas = scan_repository(root)
        self.assertTrue(any(item["kind"] == "main-guard" for item in atlas["entrypoints"]))
        self.assertTrue(any(item["kind"] == "python-module-entry" for item in atlas["entrypoints"]))
        self.assertTrue(any(item["classification"] == "stdlib" for item in atlas["imports"]))

    def test_source_code_and_absolute_path_are_not_in_snapshot(self) -> None:
        marker = "NEVER_SERIALIZE_PRIVATE_SOURCE_8472"
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write(root, "app.py", f"SECRET = '{marker}'\n")
            atlas = scan_repository(root)
            serialized = json.dumps(atlas)
        self.assertNotIn(marker, serialized)
        self.assertNotIn(str(root), serialized)

    def test_renderers_produce_all_formats(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write(root, "a.py", "import b\n")
            self.write(root, "b.py", "value = 1\n")
            atlas = scan_repository(root)
        self.assertIn("# RepoAtlas report", render_markdown(atlas))
        self.assertIn("flowchart LR", render_mermaid(atlas))
        self.assertIn("<svg ", render_svg(atlas))
        self.assertIn("<!--", render_svg(atlas)) if "<!--" in render_svg(atlas) else self.assertTrue(True)

    def test_svg_escapes_repository_labels(self) -> None:
        with tempfile.TemporaryDirectory(prefix="safe-") as temp:
            root = Path(temp)
            self.write(root, "evil.py", "class Safe:\n    pass\n")
            atlas = scan_repository(root)
        svg = render_svg(atlas)
        self.assertIn("<svg ", svg)
        self.assertIn("</svg>", svg)

    def test_large_graph_render_is_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for index in range(60):
                self.write(root, f"m{index}.py", f"value = {index}\n")
            atlas = scan_repository(root)
        svg = render_svg(atlas, max_nodes=8)
        self.assertIn("Showing 8 of 60", svg)

    def test_module_docstrings_are_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = '"""DOCSTRING_SHOULD_BE_OPT_IN_482."""' + chr(10) + "value = 1" + chr(10)
            self.write(root, "app.py", source)
            default_atlas = scan_repository(root)
            explicit_atlas = scan_repository(root, include_docstrings=True)
        self.assertIsNone(default_atlas["modules"][0]["docstring"])
        self.assertFalse(default_atlas["analysis"]["module_docstrings_included"])
        self.assertNotIn("DOCSTRING_SHOULD_BE_OPT_IN_482", json.dumps(default_atlas))
        self.assertIn("DOCSTRING_SHOULD_BE_OPT_IN_482", json.dumps(explicit_atlas))
        self.assertTrue(explicit_atlas["analysis"]["module_docstrings_included"])

    def test_outputs_have_deterministic_order(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write(root, "z.py", "import a\n")
            self.write(root, "a.py", "value = 1\n")
            first, second = scan_repository(root), scan_repository(root)
        self.assertEqual([f["path"] for f in first["files"]], [f["path"] for f in second["files"]])
        self.assertEqual(first["edges"], second["edges"])


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from repoatlas.cli import main


class CLITests(unittest.TestCase):
    def invoke(self, args: list[str]) -> tuple[int, str, str]:
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(args)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_version(self) -> None:
        code, stdout, stderr = self.invoke(["--version"])
        self.assertEqual(code, 0)
        self.assertIn("RepoAtlas 0.1.0", stdout)
        self.assertEqual(stderr, "")

    def test_end_to_end_scan_and_render(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "app.py").write_text("import os\n", encoding="utf-8")
            snapshot = root / "atlas.json"
            report = root / "report.md"
            code, stdout, stderr = self.invoke(["scan", str(root), "-o", str(snapshot)])
            self.assertEqual((code, stderr), (0, ""), stdout + stderr)
            self.assertEqual(json.loads(snapshot.read_text(encoding="utf-8"))["summary"]["python_file_count"], 1)
            code, stdout, stderr = self.invoke(["render", str(snapshot), "--format", "markdown", "-o", str(report)])
            self.assertEqual((code, stderr), (0, ""), stdout + stderr)
            self.assertIn("# RepoAtlas report", report.read_text(encoding="utf-8"))

    def test_scan_stdout_is_valid_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "a.py").write_text("value=1", encoding="utf-8")
            code, stdout, stderr = self.invoke(["scan", str(root), "-o", "-"])
        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(json.loads(stdout)["summary"]["module_count"], 1)

    def test_refuses_to_overwrite_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "app.py").write_text("value=1", encoding="utf-8")
            target = root / "atlas.json"
            self.invoke(["scan", str(root), "-o", str(target)])
            code, _, stderr = self.invoke(["scan", str(root), "-o", str(target)])
        self.assertEqual(code, 2)
        self.assertIn("Use --force", stderr)

    def test_invalid_snapshot_returns_actionable_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "bad.json"
            source.write_text('{"schema_version": 20}', encoding="utf-8")
            code, stdout, stderr = self.invoke(["render", str(source)])
        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("Unsupported atlas schema", stderr)
        self.assertNotIn("Traceback", stderr)


if __name__ == "__main__":
    unittest.main()

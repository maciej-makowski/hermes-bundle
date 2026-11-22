"""Tests for design-doc-edit: scope, refusal, atomicity, registered surface.

The plugin directory name contains a hyphen, so the module is loaded from its file path
rather than imported by name.
"""
import importlib.util
import json
import os
import pathlib
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
MODULE_PATH = HERE.parent / "__init__.py"

spec = importlib.util.spec_from_file_location("design_doc_edit", MODULE_PATH)
dd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dd)


class StubContext:
    def __init__(self):
        self.tools = {}

    def register_tool(self, name, toolset, schema, handler, description=""):
        self.tools[name] = {
            "toolset": toolset,
            "schema": schema,
            "handler": handler,
            "description": description,
        }


class ApplyEditTests(unittest.TestCase):
    def test_literal_default_count_is_one(self):
        new, count = dd._apply_edit("alpha beta alpha", {"find": "beta", "replace": "gamma"})
        self.assertEqual(count, 1)
        self.assertEqual(new, "alpha gamma alpha")

    def test_wrong_count_refuses(self):
        new, error = dd._apply_edit("alpha beta alpha", {"find": "alpha", "replace": "x"})
        self.assertIsNone(new)
        self.assertIn("match count 2", error)

    def test_expected_count_allows_multiple(self):
        new, count = dd._apply_edit(
            "alpha beta alpha", {"find": "alpha", "replace": "x", "expected_count": 2}
        )
        self.assertEqual(count, 2)
        self.assertEqual(new, "x beta x")

    def test_regex_requires_expected_count(self):
        new, error = dd._apply_edit("abc", {"find": "a.c", "replace": "x", "regex": True})
        self.assertIsNone(new)
        self.assertIn("expected_count is required", error)

    def test_identical_find_and_replace_refuses(self):
        new, error = dd._apply_edit("abc", {"find": "a", "replace": "a"})
        self.assertIsNone(new)
        self.assertIn("identical", error)


class FileEditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        self.doc = self.root / "doc.md"
        self.doc.write_text("one\ntwo\n", encoding="utf-8")
        self._old_roots = dd._DEFAULT_ROOTS
        self._old_log = dd._LOG_PATH
        self._old_roots_path = dd._ROOTS_PATH
        dd._DEFAULT_ROOTS = [str(self.root)]
        dd._LOG_PATH = str(self.root / "edits.jsonl")
        dd._ROOTS_PATH = str(self.root / "roots.json")  # absent, so the default root applies
        dd._ROOTS_LOGGED.clear()

    def tearDown(self):
        dd._DEFAULT_ROOTS = self._old_roots
        dd._LOG_PATH = self._old_log
        dd._ROOTS_PATH = self._old_roots_path
        self.tmp.cleanup()

    def log_lines(self):
        path = pathlib.Path(dd._LOG_PATH)
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

    def test_replace_applies_and_logs_fields(self):
        result = json.loads(
            dd._edit_file(str(self.doc), [{"find": "one", "replace": "1"}], "doc_replace", None)
        )
        self.assertTrue(result["success"])
        self.assertEqual(self.doc.read_text(encoding="utf-8"), "1\ntwo\n")
        lines = self.log_lines()
        self.assertEqual(len(lines), 1)
        entry = lines[0]
        self.assertEqual(entry["tool"], "doc_replace")
        self.assertEqual(entry["path"], str(self.doc))
        self.assertTrue(entry["ok"])
        self.assertIn("sha256_before", entry)
        self.assertEqual(entry["sha256_after"], result["sha256_after"])

    def test_batch_success_applies_both_edits(self):
        result = json.loads(
            dd._edit_file(
                str(self.doc),
                [{"find": "one", "replace": "1"}, {"find": "two", "replace": "2"}],
                "doc_batch",
                None,
            )
        )
        self.assertTrue(result["success"])
        self.assertEqual([r["replacements"] for r in result["replacements"]], [1, 1])
        self.assertEqual(self.doc.read_text(encoding="utf-8"), "1\n2\n")

    def test_batch_is_all_or_nothing(self):
        before = self.doc.read_bytes()
        edits = [
            {"find": "one", "replace": "1"},
            {"find": "missing", "replace": "x"},  # count 0 != 1
        ]
        result = json.loads(dd._edit_file(str(self.doc), edits, "doc_batch", None))
        self.assertFalse(result["success"])
        self.assertIn("edit 1", result["error"])
        self.assertEqual(self.doc.read_bytes(), before)
        entry = self.log_lines()[0]
        self.assertFalse(entry["ok"])
        self.assertIn("error", entry)

    def test_path_outside_roots_refuses(self):
        outside = pathlib.Path(tempfile.mkdtemp()) / "other.md"
        outside.write_text("x", encoding="utf-8")
        try:
            result = json.loads(
                dd._edit_file(str(outside), [{"find": "x", "replace": "y"}], "doc_replace", None)
            )
            self.assertFalse(result["success"])
            self.assertIn("outside the allowed roots", result["error"])
            self.assertEqual(outside.read_text(encoding="utf-8"), "x")
        finally:
            outside.unlink()
            os.rmdir(outside.parent)

    def test_symlinked_file_escape_refuses(self):
        outside = pathlib.Path(tempfile.mkdtemp()) / "secret.md"
        outside.write_text("secret\n", encoding="utf-8")
        link = self.root / "link.md"
        link.symlink_to(outside)
        try:
            result = json.loads(
                dd._edit_file(str(link), [{"find": "secret", "replace": "x"}], "doc_replace", None)
            )
            self.assertFalse(result["success"])
            self.assertIn("outside the allowed roots", result["error"])
            self.assertEqual(outside.read_text(encoding="utf-8"), "secret\n")
        finally:
            link.unlink()
            outside.unlink()
            os.rmdir(outside.parent)

    def test_symlinked_directory_escape_refuses(self):
        outside_dir = pathlib.Path(tempfile.mkdtemp())
        target = outside_dir / "secret.md"
        target.write_text("secret\n", encoding="utf-8")
        link_dir = self.root / "linked"
        link_dir.symlink_to(outside_dir, target_is_directory=True)
        try:
            result = json.loads(
                dd._edit_file(
                    str(link_dir / "secret.md"),
                    [{"find": "secret", "replace": "x"}],
                    "doc_replace",
                    None,
                )
            )
            self.assertFalse(result["success"])
            self.assertIn("outside the allowed roots", result["error"])
            self.assertEqual(target.read_text(encoding="utf-8"), "secret\n")
        finally:
            link_dir.unlink()
            target.unlink()
            os.rmdir(outside_dir)

    def test_protected_basenames_refuse(self):
        for name in (".env", ".env.staging", ".env.example", ".envrc", "prod.env", ".git"):
            path = self.root / name
            path.write_text("SECRET=1\n", encoding="utf-8")
            result = json.loads(
                dd._edit_file(
                    str(path), [{"find": "SECRET=1", "replace": "SECRET=2"}], "doc_replace", None
                )
            )
            self.assertFalse(result["success"], name)
            self.assertIn("protected", result["error"], name)
            self.assertEqual(path.read_text(encoding="utf-8"), "SECRET=1\n", name)

    def test_git_internals_refuse(self):
        gitdir = self.root / ".git"
        gitdir.mkdir()
        config = gitdir / "config"
        config.write_text("[core]\n", encoding="utf-8")
        result = json.loads(
            dd._edit_file(str(config), [{"find": "core", "replace": "x"}], "doc_replace", None)
        )
        self.assertFalse(result["success"])
        self.assertIn(".git is a protected path", result["error"])
        self.assertEqual(config.read_text(encoding="utf-8"), "[core]\n")

    def test_nul_path_refuses_and_logs(self):
        result = json.loads(
            dd._edit_file("bad\0path", [{"find": "a", "replace": "b"}], "doc_replace", None)
        )
        self.assertFalse(result["success"])
        self.assertIn("refused", result["error"])
        self.assertFalse(self.log_lines()[0]["ok"])

    def test_malformed_roots_file_fails_closed(self):
        pathlib.Path(dd._ROOTS_PATH).write_text('[""]', encoding="utf-8")
        result = json.loads(
            dd._edit_file(str(self.doc), [{"find": "one", "replace": "1"}], "doc_replace", None)
        )
        self.assertFalse(result["success"])
        self.assertIn("roots.json is invalid", result["error"])
        self.assertEqual(self.doc.read_text(encoding="utf-8"), "one\ntwo\n")
        events = [line for line in self.log_lines() if line.get("event") == "roots_invalid"]
        self.assertEqual(len(events), 1)

    def test_valid_roots_file_narrows_scope(self):
        pathlib.Path(dd._ROOTS_PATH).write_text(
            json.dumps([str(self.root / "sub")]), encoding="utf-8"
        )
        (self.root / "sub").mkdir()
        result = json.loads(
            dd._edit_file(str(self.doc), [{"find": "one", "replace": "1"}], "doc_replace", None)
        )
        self.assertFalse(result["success"])
        self.assertIn("outside the allowed roots", result["error"])

    def test_valid_roots_file_allows_its_own_root(self):
        pathlib.Path(dd._ROOTS_PATH).write_text(json.dumps([str(self.root)]), encoding="utf-8")
        result = json.loads(
            dd._edit_file(str(self.doc), [{"find": "one", "replace": "1"}], "doc_replace", None)
        )
        self.assertTrue(result["success"])
        self.assertEqual(self.doc.read_text(encoding="utf-8"), "1\ntwo\n")

    def test_roots_file_with_nul_entry_fails_closed(self):
        pathlib.Path(dd._ROOTS_PATH).write_text(json.dumps(["\u0000bad"]), encoding="utf-8")
        result = json.loads(
            dd._edit_file(str(self.doc), [{"find": "one", "replace": "1"}], "doc_replace", None)
        )
        self.assertFalse(result["success"])
        self.assertIn("roots.json is invalid", result["error"])
        self.assertEqual(self.doc.read_text(encoding="utf-8"), "one\ntwo\n")

    def test_dangling_roots_symlink_fails_closed(self):
        pathlib.Path(dd._ROOTS_PATH).symlink_to(self.root / "missing-target.json")
        result = json.loads(
            dd._edit_file(str(self.doc), [{"find": "one", "replace": "1"}], "doc_replace", None)
        )
        self.assertFalse(result["success"])
        self.assertIn("roots.json is invalid", result["error"])

    def test_roots_invalid_logged_once_per_process(self):
        pathlib.Path(dd._ROOTS_PATH).write_text('[""]', encoding="utf-8")
        for _ in range(2):
            dd._edit_file(str(self.doc), [{"find": "one", "replace": "1"}], "doc_replace", None)
        events = [line for line in self.log_lines() if line.get("event") == "roots_invalid"]
        self.assertEqual(len(events), 1)


class RegisteredSurfaceTests(unittest.TestCase):
    def setUp(self):
        self.ctx = StubContext()
        dd.register(self.ctx)
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        self.doc = self.root / "doc.md"
        self.doc.write_text("one\ntwo\n", encoding="utf-8")
        self._old_roots = dd._DEFAULT_ROOTS
        self._old_log = dd._LOG_PATH
        self._old_roots_path = dd._ROOTS_PATH
        dd._DEFAULT_ROOTS = [str(self.root)]
        dd._LOG_PATH = str(self.root / "edits.jsonl")
        dd._ROOTS_PATH = str(self.root / "roots.json")

    def tearDown(self):
        dd._DEFAULT_ROOTS = self._old_roots
        dd._LOG_PATH = self._old_log
        dd._ROOTS_PATH = self._old_roots_path
        self.tmp.cleanup()

    def test_register_declares_both_tools(self):
        self.assertEqual(set(self.ctx.tools), {"doc_replace", "doc_batch"})
        for name, entry in self.ctx.tools.items():
            self.assertEqual(entry["toolset"], "design_doc")
            self.assertEqual(entry["schema"]["name"], name)
            self.assertTrue(callable(entry["handler"]))

    def test_registered_doc_replace_handler_works(self):
        handler = self.ctx.tools["doc_replace"]["handler"]
        result = json.loads(handler({"path": str(self.doc), "find": "one", "replace": "1"}))
        self.assertTrue(result["success"])
        self.assertEqual(self.doc.read_text(encoding="utf-8"), "1\ntwo\n")

    def test_registered_doc_batch_handler_works(self):
        handler = self.ctx.tools["doc_batch"]["handler"]
        result = json.loads(
            handler(
                {
                    "path": str(self.doc),
                    "edits": [{"find": "one", "replace": "1"}, {"find": "two", "replace": "2"}],
                }
            )
        )
        self.assertTrue(result["success"])
        self.assertEqual(self.doc.read_text(encoding="utf-8"), "1\n2\n")


if __name__ == "__main__":
    unittest.main()

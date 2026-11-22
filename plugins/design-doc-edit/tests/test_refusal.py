"""Tests for design-doc-edit: count-check refusal and batch atomicity.

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
        dd._DEFAULT_ROOTS = [str(self.root)]
        dd._LOG_PATH = str(self.root / "edits.jsonl")

    def tearDown(self):
        dd._DEFAULT_ROOTS = self._old_roots
        dd._LOG_PATH = self._old_log
        self.tmp.cleanup()

    def test_replace_applies_and_logs(self):
        result = json.loads(
            dd._edit_file(str(self.doc), [{"find": "one", "replace": "1"}], "doc_replace", None)
        )
        self.assertTrue(result["success"])
        self.assertEqual(self.doc.read_text(encoding="utf-8"), "1\ntwo\n")
        self.assertTrue((self.root / "edits.jsonl").read_text(encoding="utf-8").strip())

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

    def test_protected_basename_refuses(self):
        env = self.root / ".env"
        env.write_text("SECRET=1\n", encoding="utf-8")
        result = json.loads(
            dd._edit_file(str(env), [{"find": "SECRET=1", "replace": "SECRET=2"}], "doc_replace", None)
        )
        self.assertFalse(result["success"])
        self.assertIn("protected", result["error"])
        self.assertEqual(env.read_text(encoding="utf-8"), "SECRET=1\n")


if __name__ == "__main__":
    unittest.main()

"""Tests for design-doc-edit: scope, refusal, atomicity, registered surface.

The plugin directory name contains a hyphen, so the module is loaded from its file path
rather than imported by name.
"""
import hashlib
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

    def test_batch_success_logs_one_record(self):
        result = json.loads(
            dd._edit_file(
                str(self.doc),
                [{"find": "one", "replace": "1"}, {"find": "two", "replace": "2"}],
                "doc_batch",
                None,
            )
        )
        self.assertTrue(result["success"])
        lines = self.log_lines()
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]["tool"], "doc_batch")
        self.assertTrue(lines[0]["ok"])

    def test_log_directory_is_created(self):
        dd._LOG_PATH = str(self.root / "deep" / "log" / "edits.jsonl")
        result = json.loads(
            dd._edit_file(str(self.doc), [{"find": "one", "replace": "1"}], "doc_replace", None)
        )
        self.assertTrue(result["success"])
        self.assertTrue((self.root / "deep" / "log" / "edits.jsonl").exists())

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

    def test_batch_applies_in_order(self):
        self.doc.write_text("two\n", encoding="utf-8")
        result = json.loads(
            dd._edit_file(
                str(self.doc),
                [{"find": "two", "replace": "one"}, {"find": "one", "replace": "zero"}],
                "doc_batch",
                None,
            )
        )
        self.assertTrue(result["success"])
        self.assertEqual(self.doc.read_text(encoding="utf-8"), "zero\n")

    def test_regex_count_mismatch_refuses(self):
        self.doc.write_text("aaa\n", encoding="utf-8")
        result = json.loads(
            dd._edit_file(
                str(self.doc),
                [{"find": "a", "replace": "b", "regex": True, "expected_count": 2}],
                "doc_replace",
                None,
            )
        )
        self.assertFalse(result["success"])
        self.assertIn("match count 3", result["error"])
        self.assertEqual(self.doc.read_text(encoding="utf-8"), "aaa\n")

    def test_regex_replaces_every_match(self):
        self.doc.write_text("aaa\n", encoding="utf-8")
        result = json.loads(
            dd._edit_file(
                str(self.doc),
                [{"find": "a", "replace": "b", "regex": True, "expected_count": 3}],
                "doc_replace",
                None,
            )
        )
        self.assertTrue(result["success"])
        self.assertEqual(self.doc.read_text(encoding="utf-8"), "bbb\n")

    def test_regex_is_case_sensitive(self):
        self.doc.write_text("A a\n", encoding="utf-8")
        result = json.loads(
            dd._edit_file(
                str(self.doc),
                [{"find": "a", "replace": "b", "regex": True, "expected_count": 1}],
                "doc_replace",
                None,
            )
        )
        self.assertTrue(result["success"])
        self.assertEqual(self.doc.read_text(encoding="utf-8"), "A b\n")

    def test_literal_match_is_case_sensitive(self):
        self.doc.write_text("Alpha alpha alpha\n", encoding="utf-8")
        result = json.loads(
            dd._edit_file(
                str(self.doc), [{"find": "Alpha", "replace": "X"}], "doc_replace", None
            )
        )
        self.assertTrue(result["success"])
        self.assertEqual(self.doc.read_text(encoding="utf-8"), "X alpha alpha\n")

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
        self.assertEqual(len(self.log_lines()), 1)

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
            self.assertEqual(len(self.log_lines()), 1)
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

    def test_symlink_to_protected_file_refuses(self):
        env = self.root / ".env"
        env.write_text("SECRET=1\n", encoding="utf-8")
        link = self.root / "innocent.md"
        link.symlink_to(env)
        try:
            result = json.loads(
                dd._edit_file(
                    str(link), [{"find": "SECRET=1", "replace": "SECRET=2"}], "doc_replace", None
                )
            )
            self.assertFalse(result["success"])
            self.assertIn("protected", result["error"])
            self.assertEqual(env.read_text(encoding="utf-8"), "SECRET=1\n")
        finally:
            link.unlink()

    def test_symlink_to_git_internals_refuses(self):
        gitdir = self.root / ".git"
        gitdir.mkdir()
        config = gitdir / "config"
        config.write_text("[core]\n", encoding="utf-8")
        link = self.root / "innocent2.md"
        link.symlink_to(config)
        try:
            result = json.loads(
                dd._edit_file(str(link), [{"find": "core", "replace": "x"}], "doc_replace", None)
            )
            self.assertFalse(result["success"])
            self.assertIn(".git is a protected path", result["error"])
            self.assertEqual(config.read_text(encoding="utf-8"), "[core]\n")
        finally:
            link.unlink()

    def test_protected_basenames_refuse(self):
        for name in (".env", ".env.staging", ".env.example", ".envrc", "prod.env", "prod.envrc", ".git"):
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
        self.assertEqual(len(self.log_lines()), 7)

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
        self.assertEqual(len(self.log_lines()), 1)

    def test_nul_path_refuses_and_logs(self):
        result = json.loads(
            dd._edit_file("bad\0path", [{"find": "a", "replace": "b"}], "doc_replace", None)
        )
        self.assertFalse(result["success"])
        self.assertIn("refused", result["error"])
        self.assertFalse(self.log_lines()[0]["ok"])
        self.assertEqual(len(self.log_lines()), 1)

    def test_malformed_roots_file_fails_closed(self):
        pathlib.Path(dd._ROOTS_PATH).write_text('[""]', encoding="utf-8")
        result = json.loads(
            dd._edit_file(str(self.doc), [{"find": "one", "replace": "1"}], "doc_replace", None)
        )
        self.assertFalse(result["success"])
        self.assertIn("roots.json is invalid", result["error"])
        self.assertIn("non-empty list", result["error"])
        self.assertEqual(self.doc.read_text(encoding="utf-8"), "one\ntwo\n")
        lines = self.log_lines()
        self.assertEqual(len(lines), 2)  # roots_invalid event plus the call record
        events = [line for line in lines if line.get("event") == "roots_invalid"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["path"], dd._ROOTS_PATH)
        self.assertIn("non-empty list", events[0]["error"])
        records = [line for line in lines if "ok" in line]
        self.assertEqual(len(records), 1)
        self.assertFalse(records[0]["ok"])

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
        events = [line for line in self.log_lines() if line.get("event") == "roots_invalid"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["path"], dd._ROOTS_PATH)
        self.assertIn("null", events[0]["error"].lower())

    def test_dangling_roots_symlink_fails_closed(self):
        pathlib.Path(dd._ROOTS_PATH).symlink_to(self.root / "missing-target.json")
        result = json.loads(
            dd._edit_file(str(self.doc), [{"find": "one", "replace": "1"}], "doc_replace", None)
        )
        self.assertFalse(result["success"])
        self.assertIn("roots.json is invalid", result["error"])
        events = [line for line in self.log_lines() if line.get("event") == "roots_invalid"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["path"], dd._ROOTS_PATH)
        self.assertIn("No such file", events[0]["error"])

    def test_roots_empty_list_fails_closed(self):
        pathlib.Path(dd._ROOTS_PATH).write_text("[]", encoding="utf-8")
        result = json.loads(
            dd._edit_file(str(self.doc), [{"find": "one", "replace": "1"}], "doc_replace", None)
        )
        self.assertFalse(result["success"])
        self.assertIn("non-empty list", result["error"])
        lines = self.log_lines()
        self.assertEqual(len(lines), 2)
        events = [line for line in lines if line.get("event") == "roots_invalid"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["path"], dd._ROOTS_PATH)
        self.assertIn("non-empty list", events[0]["error"])
        self.assertFalse([line for line in lines if "ok" in line][0]["ok"])

    def test_roots_non_string_entry_fails_closed(self):
        pathlib.Path(dd._ROOTS_PATH).write_text("[1]", encoding="utf-8")
        result = json.loads(
            dd._edit_file(str(self.doc), [{"find": "one", "replace": "1"}], "doc_replace", None)
        )
        self.assertFalse(result["success"])
        self.assertIn("non-empty list", result["error"])
        lines = self.log_lines()
        self.assertEqual(len(lines), 2)
        events = [line for line in lines if line.get("event") == "roots_invalid"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["path"], dd._ROOTS_PATH)
        self.assertIn("non-empty list", events[0]["error"])
        self.assertFalse([line for line in lines if "ok" in line][0]["ok"])

    def test_roots_invalid_json_fails_closed(self):
        pathlib.Path(dd._ROOTS_PATH).write_text("{not json", encoding="utf-8")
        result = json.loads(
            dd._edit_file(str(self.doc), [{"find": "one", "replace": "1"}], "doc_replace", None)
        )
        self.assertFalse(result["success"])
        self.assertIn("roots.json is invalid", result["error"])
        lines = self.log_lines()
        self.assertEqual(len(lines), 2)
        events = [line for line in lines if line.get("event") == "roots_invalid"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["path"], dd._ROOTS_PATH)
        self.assertTrue(events[0]["error"])
        self.assertFalse([line for line in lines if "ok" in line][0]["ok"])

    def test_multiple_roots_allow_either(self):
        other = pathlib.Path(tempfile.mkdtemp())
        doc2 = other / "doc2.md"
        doc2.write_text("one\n", encoding="utf-8")
        pathlib.Path(dd._ROOTS_PATH).write_text(
            json.dumps([str(self.root), str(other)]), encoding="utf-8"
        )
        try:
            first = json.loads(
                dd._edit_file(str(self.doc), [{"find": "one", "replace": "1"}], "doc_replace", None)
            )
            second = json.loads(
                dd._edit_file(str(doc2), [{"find": "one", "replace": "1"}], "doc_replace", None)
            )
            self.assertTrue(first["success"])
            self.assertTrue(second["success"])
        finally:
            doc2.unlink()
            other.rmdir()

    def test_root_slash_allows_any_path(self):
        pathlib.Path(dd._ROOTS_PATH).write_text(json.dumps(["/"]), encoding="utf-8")
        result = json.loads(
            dd._edit_file(str(self.doc), [{"find": "one", "replace": "1"}], "doc_replace", None)
        )
        self.assertTrue(result["success"])

    def test_roots_invalid_logged_once_per_process(self):
        pathlib.Path(dd._ROOTS_PATH).write_text('[""]', encoding="utf-8")
        for _ in range(2):
            dd._edit_file(str(self.doc), [{"find": "one", "replace": "1"}], "doc_replace", None)
        events = [line for line in self.log_lines() if line.get("event") == "roots_invalid"]
        self.assertEqual(len(events), 1)
        self.assertEqual(len(self.log_lines()), 3)  # one event plus two call records


class LimitsAndAtomicityTests(unittest.TestCase):
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
        dd._ROOTS_PATH = str(self.root / "roots.json")
        dd._ROOTS_LOGGED.clear()

    def tearDown(self):
        dd._DEFAULT_ROOTS = self._old_roots
        dd._LOG_PATH = self._old_log
        dd._ROOTS_PATH = self._old_roots_path
        self.tmp.cleanup()

    def test_sibling_prefix_directory_refuses(self):
        sibling = pathlib.Path(str(self.root) + "-evil")
        sibling.mkdir()
        target = sibling / "doc.md"
        target.write_text("one\n", encoding="utf-8")
        try:
            result = json.loads(
                dd._edit_file(str(target), [{"find": "one", "replace": "1"}], "doc_replace", None)
            )
            self.assertFalse(result["success"])
            self.assertIn("outside the allowed roots", result["error"])
            self.assertEqual(target.read_text(encoding="utf-8"), "one\n")
        finally:
            target.unlink()
            sibling.rmdir()

    def test_size_limit_refuses(self):
        big = self.root / "big.md"
        with open(big, "wb") as f:
            f.truncate(dd._MAX_BYTES + 1)
        result = json.loads(
            dd._edit_file(str(big), [{"find": "x", "replace": "y"}], "doc_replace", None)
        )
        self.assertFalse(result["success"])
        self.assertIn("larger than", result["error"])

    def test_edit_count_limit_refuses(self):
        edits = [{"find": "one", "replace": str(i)} for i in range(dd._MAX_EDITS + 1)]
        result = json.loads(dd._edit_file(str(self.doc), edits, "doc_batch", None))
        self.assertFalse(result["success"])
        self.assertIn("more than", result["error"])

    def test_exact_size_limit_is_allowed(self):
        big = self.root / "exact.md"
        big.write_bytes(b"one\n" + b"a" * (dd._MAX_BYTES - 4))
        result = json.loads(
            dd._edit_file(str(big), [{"find": "one", "replace": "1"}], "doc_replace", None)
        )
        self.assertTrue(result["success"])

    def test_exact_edit_count_limit_is_allowed(self):
        self.doc.write_text(
            "".join(f"l{i}\n" for i in range(dd._MAX_EDITS)), encoding="utf-8"
        )
        edits = [{"find": f"l{i}\n", "replace": f"L{i}\n"} for i in range(dd._MAX_EDITS)]
        result = json.loads(dd._edit_file(str(self.doc), edits, "doc_batch", None))
        self.assertTrue(result["success"])

    def test_chown_failure_still_writes(self):
        from unittest import mock

        with mock.patch("os.chown", side_effect=OSError("nope")):
            result = json.loads(
                dd._edit_file(str(self.doc), [{"find": "one", "replace": "1"}], "doc_replace", None)
            )
        self.assertTrue(result["success"])
        self.assertEqual(self.doc.read_text(encoding="utf-8"), "1\ntwo\n")

    def test_chown_uses_original_owner(self):
        from unittest import mock

        st = os.stat(self.doc)
        with mock.patch("os.chown") as chown:
            result = json.loads(
                dd._edit_file(str(self.doc), [{"find": "one", "replace": "1"}], "doc_replace", None)
            )
        self.assertTrue(result["success"])
        chown.assert_called_once()
        args = chown.call_args[0]
        self.assertEqual(args[1], st.st_uid)
        self.assertEqual(args[2], st.st_gid)

    def test_non_utf8_refuses(self):
        bad = self.root / "bad.md"
        bad.write_bytes(b"\xff\xfe\x00binary")
        result = json.loads(
            dd._edit_file(str(bad), [{"find": "a", "replace": "b"}], "doc_replace", None)
        )
        self.assertFalse(result["success"])

    def test_regex_success_with_backreference(self):
        result = json.loads(
            dd._edit_file(
                str(self.doc),
                [{"find": "(one)", "replace": "[\\1]", "regex": True, "expected_count": 1}],
                "doc_replace",
                None,
            )
        )
        self.assertTrue(result["success"])
        self.assertEqual(self.doc.read_text(encoding="utf-8"), "[one]\ntwo\n")

    def test_empty_replace_deletes(self):
        result = json.loads(
            dd._edit_file(str(self.doc), [{"find": "two\n", "replace": ""}], "doc_replace", None)
        )
        self.assertTrue(result["success"])
        self.assertEqual(self.doc.read_text(encoding="utf-8"), "one\n")

    def test_result_carries_sha256_and_note(self):
        result = json.loads(
            dd._edit_file(str(self.doc), [{"find": "one", "replace": "1"}], "doc_replace", None)
        )
        expected = hashlib.sha256(self.doc.read_bytes()).hexdigest()
        self.assertEqual(result["sha256_after"], expected)
        self.assertIn("re-read", result["note"])

    def test_mode_preserved(self):
        os.chmod(self.doc, 0o640)
        result = json.loads(
            dd._edit_file(str(self.doc), [{"find": "one", "replace": "1"}], "doc_replace", None)
        )
        self.assertTrue(result["success"])
        self.assertEqual(os.stat(self.doc).st_mode & 0o777, 0o640)

    def test_no_temp_files_after_success(self):
        dd._edit_file(str(self.doc), [{"find": "one", "replace": "1"}], "doc_replace", None)
        leftovers = [p.name for p in self.root.iterdir() if p.name.startswith(".docedit-")]
        self.assertEqual(leftovers, [])

    def test_replace_failure_leaves_original_and_cleans_temp(self):
        from unittest import mock

        with mock.patch("os.replace", side_effect=OSError("boom")):
            result = json.loads(
                dd._edit_file(str(self.doc), [{"find": "one", "replace": "1"}], "doc_replace", None)
            )
        self.assertFalse(result["success"])
        self.assertEqual(self.doc.read_text(encoding="utf-8"), "one\ntwo\n")
        leftovers = [p.name for p in self.root.iterdir() if p.name.startswith(".docedit-")]
        self.assertEqual(leftovers, [])

    def test_fsync_called_for_file_and_directory(self):
        from unittest import mock

        calls = []
        real = os.fsync

        def counting(fd):
            calls.append(fd)
            return real(fd)

        with mock.patch("os.fsync", side_effect=counting):
            result = json.loads(
                dd._edit_file(str(self.doc), [{"find": "one", "replace": "1"}], "doc_replace", None)
            )
        self.assertTrue(result["success"])
        self.assertGreaterEqual(len(calls), 2)


class DefaultsTests(unittest.TestCase):
    def test_documented_defaults(self):
        self.assertEqual(dd._PLUGIN_DIR, str(MODULE_PATH.parent))
        self.assertEqual(dd._DEFAULT_ROOTS, ["/home/hermes/hermes-designs"])
        self.assertEqual(dd._MAX_BYTES, 8 * 1024 * 1024)
        self.assertEqual(dd._MAX_EDITS, 200)
        self.assertEqual(dd._LOG_PATH, os.path.join(dd._PLUGIN_DIR, "log", "edits.jsonl"))
        self.assertEqual(dd._ROOTS_PATH, os.path.join(dd._PLUGIN_DIR, "roots.json"))


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

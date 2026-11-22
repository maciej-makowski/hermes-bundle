"""design-doc-edit — scoped, atomic, count-checked editing tools for design docs.

Registered tools (toolset: design_doc):

- doc_replace: one literal or regex replacement, occurrence-count checked,
  applied atomically (temp file + rename, mode preserved, owner preserved when permitted).
- doc_batch:   many replacements in one call, applied in order against the
  evolving content, all-or-nothing, atomic.

Scope is enforced in code, not by an LLM: the target path's real path must sit
under one of the roots in roots.json (next to this file). Protected paths
(.env, .env.*, *.env, *.envrc, .git) are always refused. No subprocesses, no
network. Every call, success or failure, appends one JSON line to
log/edits.jsonl (a malformed roots.json adds one roots_invalid line, once per
process).
"""

import hashlib
import json
import os
import re
import tempfile
import time

_TOOLSET = "design_doc"
_PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
_LOG_PATH = os.path.join(_PLUGIN_DIR, "log", "edits.jsonl")
_ROOTS_PATH = os.path.join(_PLUGIN_DIR, "roots.json")
_DEFAULT_ROOTS = ["/home/hermes/hermes-designs"]
_PROTECTED_SUFFIXES = (".env", ".envrc")
_ROOTS_LOGGED = set()


def _protected_reason(name, rp):
    """Return a refusal reason when the path is protected, else None."""
    parts = rp.split(os.sep)
    if ".git" in parts:
        return ".git is a protected path"
    if name == ".env" or name.startswith(".env.") or name.endswith(_PROTECTED_SUFFIXES):
        return f"{name} is a protected path"
    return None
_MAX_BYTES = 8 * 1024 * 1024
_MAX_EDITS = 200


def _log(entry):
    try:
        os.makedirs(os.path.dirname(_LOG_PATH), exist_ok=True)
        with open(_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, sort_keys=True) + "\n")
    except Exception:
        pass  # logging must never break the tool


def _roots_failure(message):
    if message not in _ROOTS_LOGGED:
        _ROOTS_LOGGED.add(message)
        _log({
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "event": "roots_invalid",
            "path": _ROOTS_PATH,
            "error": message,
        })
    return [], f"roots.json is invalid ({message}); fix or remove it next to the plugin"


def _roots():
    if not os.path.lexists(_ROOTS_PATH):
        roots = _DEFAULT_ROOTS
    else:
        try:
            with open(_ROOTS_PATH, encoding="utf-8") as f:
                data = json.load(f)
            if not (isinstance(data, list) and data and all(isinstance(r, str) and r for r in data)):
                raise ValueError("roots.json must be a non-empty list of non-empty strings")
            roots = data
        except (OSError, ValueError) as exc:
            return _roots_failure(str(exc))
    try:
        return [os.path.realpath(r) for r in roots], None
    except (OSError, ValueError) as exc:
        return _roots_failure(str(exc))


def _check_scope(path):
    """Return (realpath, None) on success or (None, error) on refusal."""
    if not isinstance(path, str) or not path.strip():
        return None, "path is required"
    try:
        rp = os.path.realpath(path)
    except (OSError, ValueError) as exc:
        return None, f"refused: {exc}"
    allowed, roots_error = _roots()
    if roots_error:
        return None, f"refused: {roots_error}"
    if not any(rp == r or rp.startswith(r + os.sep) for r in allowed):
        return None, (
            f"refused: {path} resolves to {rp}, outside the allowed roots {allowed}; "
            "edit roots.json next to the plugin to widen scope"
        )
    reason = _protected_reason(os.path.basename(rp), rp)
    if reason:
        return None, f"refused: {reason}"
    return rp, None


def _read(path):
    with open(path, "rb") as f:
        raw = f.read(_MAX_BYTES + 1)
    if len(raw) > _MAX_BYTES:
        raise ValueError(f"file larger than {_MAX_BYTES} bytes — refusing")
    return raw, raw.decode("utf-8")  # strict: non-UTF-8 files fail loudly


def _apply_edit(content, edit):
    """Apply one edit to content. Return (new_content, count) or (None, error)."""
    if not isinstance(edit, dict):
        return None, "each edit must be an object with find/replace"
    find = edit.get("find")
    replace = edit.get("replace", "")
    if not isinstance(find, str) or not find:
        return None, "find must be a non-empty string"
    if not isinstance(replace, str):
        return None, "replace must be a string"
    if find == replace:
        return None, "find and replace are identical — nothing to do"
    regex = bool(edit.get("regex", False))
    expected = edit.get("expected_count")
    if regex:
        if expected is None:
            return None, "expected_count is required when regex is true"
        try:
            pattern = re.compile(find)
        except re.error as exc:
            return None, f"bad regex: {exc}"
        new, count = pattern.subn(replace, content)
    else:
        count = content.count(find)
        if expected is None:
            expected = 1
        new = content.replace(find, replace)
    if count != expected:
        return None, (
            f"match count {count} != expected_count {expected} — nothing changed; "
            "re-read the file and fix the find text or the count"
        )
    return new, count


def _edit_file(path, edits, tool, task_id):
    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "tool": tool,
        "task_id": task_id,
        "path": path,
    }

    def done(payload):
        entry["ok"] = bool(payload.get("success"))
        if not payload.get("success"):
            entry["error"] = payload.get("error")
        _log(entry)
        return json.dumps(payload, sort_keys=True)

    try:
        rp, err = _check_scope(path)
        if err:
            return done({"success": False, "error": err})
        if not edits or not isinstance(edits, list):
            raise ValueError("edits must be a non-empty list")
        if len(edits) > _MAX_EDITS:
            raise ValueError(f"more than {_MAX_EDITS} edits — refusing")
        if not os.path.isfile(rp):
            raise ValueError(f"not a regular file: {path}")
        raw, content = _read(rp)
        entry["sha256_before"] = hashlib.sha256(raw).hexdigest()
        results = []
        for i, edit in enumerate(edits):
            new, count = _apply_edit(content, edit)
            if new is None:
                raise ValueError(f"edit {i}: {count}")
            results.append({"index": i, "replacements": count})
            content = new
        data = content.encode("utf-8")
        st = os.stat(rp)
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(rp), prefix=".docedit-", suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            os.chmod(tmp, st.st_mode)
            try:
                os.chown(tmp, st.st_uid, st.st_gid)  # keep owner when permitted
            except OSError:
                pass
            os.replace(tmp, rp)
            try:
                dfd = os.open(os.path.dirname(rp), os.O_DIRECTORY)
                try:
                    os.fsync(dfd)
                finally:
                    os.close(dfd)
            except OSError:
                pass
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
        sha_after = hashlib.sha256(data).hexdigest()
        entry["sha256_after"] = sha_after
        entry["edits"] = len(edits)
        return done({
            "success": True,
            "path": path,
            "replacements": results,
            "sha256_after": sha_after,
            "note": "file changed on disk — re-read it with read_file before further patch/write_file edits",
        })
    except Exception as exc:
        return done({"success": False, "error": str(exc)})


def _make_handler(tool):
    def handler(params, **kwargs):
        return _edit_file(
            params.get("path"),
            params.get("edits") if tool == "doc_batch" else [params],
            tool,
            kwargs.get("task_id"),
        )
    return handler


_DOC_REPLACE_SCHEMA = {
    "name": "doc_replace",
    "description": (
        "One replacement inside a design doc, atomic and occurrence-count checked. "
        "Literal by default: find must occur exactly once unless expected_count says otherwise. "
        "regex=true requires expected_count. Scoped to the plugin's allowed roots; refuses "
        ".env/.git paths. Non-UTF-8 and >8 MB files refused. Returns the new file sha256; "
        "re-read the file before further patch/write_file edits."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Absolute path of the doc inside an allowed design root"},
            "find": {"type": "string", "description": "Exact text to find (regex when regex=true)"},
            "replace": {"type": "string", "description": "Replacement text; may be empty to delete"},
            "expected_count": {
                "type": "integer",
                "description": "Required occurrences of find (default 1 for literal; REQUIRED for regex)",
            },
            "regex": {"type": "boolean", "description": "Treat find as a Python regex; replace may use backrefs"},
        },
        "required": ["path", "find", "replace"],
    },
}

_DOC_BATCH_SCHEMA = {
    "name": "doc_batch",
    "description": (
        "Many replacements in one call, applied in order against the evolving content, "
        "all-or-nothing: if any edit fails its count check, NOTHING is written. Same scope "
        "and limits as doc_replace. Returns per-edit replacement counts and the new sha256; "
        "re-read the file before further patch/write_file edits."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Absolute path of the doc inside an allowed design root"},
            "edits": {
                "type": "array",
                "minItems": 1,
                "description": "Edits in application order; each: {find, replace, expected_count?, regex?}",
                "items": {
                    "type": "object",
                    "properties": {
                        "find": {"type": "string"},
                        "replace": {"type": "string"},
                        "expected_count": {"type": "integer"},
                        "regex": {"type": "boolean"},
                    },
                    "required": ["find", "replace"],
                },
            },
        },
        "required": ["path", "edits"],
    },
}


def register(ctx):
    ctx.register_tool(
        name="doc_replace",
        toolset=_TOOLSET,
        schema=_DOC_REPLACE_SCHEMA,
        handler=_make_handler("doc_replace"),
        description=_DOC_REPLACE_SCHEMA["description"],
    )
    ctx.register_tool(
        name="doc_batch",
        toolset=_TOOLSET,
        schema=_DOC_BATCH_SCHEMA,
        handler=_make_handler("doc_batch"),
        description=_DOC_BATCH_SCHEMA["description"],
    )

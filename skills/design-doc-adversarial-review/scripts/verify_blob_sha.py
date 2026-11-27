#!/usr/bin/env python3
"""Verify a pushed GitHub file's blob SHA against the intended local file.

Usage:
  python verify_blob_sha.py LOCAL_FILE [SPILL_FILE ...]

- Prints the git blob SHA1 of LOCAL_FILE (sha1 of b"blob <len>\\x00" + bytes).
- Warns if LOCAL_FILE does not end with a newline (markdownlint MD047 fails
  on a missing final newline).
- For each SPILL_FILE (a saved-over-budget get_file_contents result), strips
  the 'successfully downloaded text file (SHA: ...)' header, computes the
  remote blob SHA, and prints MATCH or MISMATCH against LOCAL_FILE.
  Pass the spillover path instead of re-fetching the remote file.

Exit 0 when every comparison matches, 2 on any mismatch.
"""
import hashlib
import json
import sys


def blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\x00" % len(data) + data).hexdigest()


def extract_remote(path: str) -> bytes:
    """Content of a saved get_file_contents result (JSON envelope or plain text)."""
    raw = open(path, encoding="utf-8", errors="replace").read()
    try:
        obj = json.loads(raw)
        text = obj.get("result", "") if isinstance(obj, dict) else raw
    except Exception:
        text = raw
    if not isinstance(text, str):
        text = raw
    i = text.find("successfully downloaded text file (SHA: ")
    if i != -1:
        text = text[text.find("\n", i) + 1:]
    return text.encode("utf-8")


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    local = open(argv[1], "rb").read()
    want = blob_sha(local)
    print(f"local  blob: {want}  ({len(local)} bytes)")
    if not local.endswith(b"\n"):
        print("WARN: local file does not end with a newline (MD047 will fail CI)")
    ok = True
    for spill in argv[2:]:
        remote = extract_remote(spill)
        got = blob_sha(remote)
        match = got == want
        ok = ok and match
        print(f"remote blob: {got}  ({len(remote)} bytes)  {'MATCH' if match else 'MISMATCH'}")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))

#!/usr/bin/env python3
"""manifest - File manifest generator and integrity checker.

Single-file, zero-dependency CLI. Creates checksummed file manifests for releases.
"""

import sys
import argparse
import os
import hashlib
import json
from datetime import datetime


def hash_file(path, algo="sha256"):
    h = hashlib.new(algo)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def human_size(b):
    for u in ["B", "KB", "MB", "GB"]:
        if b < 1024: return f"{b:.1f}{u}"
        b /= 1024
    return f"{b:.1f}TB"


def cmd_generate(args):
    entries = []
    for root, dirs, files in os.walk(args.path):
        dirs[:] = [d for d in dirs if d not in {".git", "__pycache__", "node_modules"}]
        for f in sorted(files):
            fp = os.path.join(root, f)
            rel = os.path.relpath(fp, args.path)
            try:
                stat = os.stat(fp)
                digest = hash_file(fp, args.algo)
                entries.append({"path": rel, "size": stat.st_size, "hash": digest,
                               "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()})
            except (PermissionError, OSError):
                pass

    if args.json:
        manifest = {"generated": datetime.now().isoformat(), "algorithm": args.algo,
                    "total_files": len(entries), "total_size": sum(e["size"] for e in entries),
                    "files": entries}
        output = json.dumps(manifest, indent=2)
    else:
        lines = [f"# Manifest ({args.algo}) — {datetime.now().isoformat()}", ""]
        for e in entries:
            lines.append(f"{e['hash']}  {human_size(e['size']):>9s}  {e['path']}")
        lines.append(f"\n# {len(entries)} files, {human_size(sum(e['size'] for e in entries))}")
        output = "\n".join(lines)

    if args.output:
        with open(args.output, "w") as f:
            f.write(output + "\n")
        print(f"  Written to {args.output} ({len(entries)} files)")
    else:
        print(output)


def cmd_verify(args):
    with open(args.manifest) as f:
        content = f.read()

    if content.strip().startswith("{"):
        data = json.loads(content)
        algo = data["algorithm"]
        entries = data["files"]
    else:
        algo = "sha256"
        entries = []
        for line in content.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"): continue
            parts = line.split(None, 2)
            if len(parts) >= 3:
                entries.append({"hash": parts[0], "path": parts[2]})
            elif len(parts) == 2:
                entries.append({"hash": parts[0], "path": parts[1]})

    ok, fail, missing = 0, 0, 0
    base = os.path.dirname(args.manifest) or "."
    for e in entries:
        fp = os.path.join(base, e["path"])
        if not os.path.exists(fp):
            print(f"  ✗ MISSING  {e['path']}")
            missing += 1
        else:
            actual = hash_file(fp, algo)
            if actual == e["hash"]:
                ok += 1
            else:
                print(f"  ✗ CHANGED  {e['path']}")
                fail += 1

    print(f"\n  ✅ {ok} OK  ❌ {fail} changed  ⚠️ {missing} missing")
    return 1 if (fail + missing) > 0 else 0


def main():
    p = argparse.ArgumentParser(prog="manifest", description="File manifest generator")
    sub = p.add_subparsers(dest="cmd")
    s = sub.add_parser("generate", aliases=["gen"], help="Generate manifest")
    s.add_argument("path", nargs="?", default=".")
    s.add_argument("-a", "--algo", default="sha256", choices=["md5", "sha1", "sha256", "sha512"])
    s.add_argument("-o", "--output")
    s.add_argument("--json", action="store_true")
    s = sub.add_parser("verify", help="Verify manifest")
    s.add_argument("manifest")
    args = p.parse_args()
    if not args.cmd: p.print_help(); return 1
    cmds = {"generate": cmd_generate, "gen": cmd_generate, "verify": cmd_verify}
    return cmds[args.cmd](args) or 0


if __name__ == "__main__":
    sys.exit(main())

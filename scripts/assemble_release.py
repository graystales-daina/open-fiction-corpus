"""Assemble a versioned release directory from built dataset exports.

Reads the .jsonl.gz files that `ofc build` wrote to dist/, arranges them in
the release layout documented in docs/hugging-face.md, and writes a build
manifest and checksums so every release is traceable to an exact catalogue
commit.

Usage:
    python scripts/assemble_release.py --version v0.1.0 --commit <sha>
"""

from __future__ import annotations

import argparse
import datetime
import gzip
import hashlib
import json
import shutil
import sys
from pathlib import Path


def row_ids(path: Path) -> list[str]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return [json.loads(line)["id"] for line in handle]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True, help="Release version, e.g. v0.1.0")
    parser.add_argument("--commit", required=True, help="Catalogue commit SHA")
    parser.add_argument("--dist", type=Path, default=Path("dist"))
    parser.add_argument("--output", type=Path, default=Path("dist/release"))
    args = parser.parse_args()

    books = args.dist / "books.jsonl.gz"
    if not books.exists():
        print(f"error: {books} not found; run `ofc build` first", file=sys.stderr)
        return 1

    if args.output.exists():
        shutil.rmtree(args.output)
    (args.output / "data").mkdir(parents=True)
    (args.output / "packs").mkdir()
    (args.output / "release").mkdir()

    files: dict[str, dict[str, object]] = {}

    shutil.copy2(books, args.output / "data" / books.name)
    files[f"data/{books.name}"] = {"works": row_ids(books)}

    for pack_file in sorted(args.dist.glob("*.jsonl.gz")):
        if pack_file.name == books.name:
            continue
        shutil.copy2(pack_file, args.output / "packs" / pack_file.name)
        files[f"packs/{pack_file.name}"] = {"works": row_ids(pack_file)}

    for entry in files.values():
        entry["row_count"] = len(entry["works"])

    manifest = {
        "version": args.version,
        "catalogue_commit": args.commit,
        "built_at": datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds"),
        "files": files,
    }
    manifest_path = args.output / "release" / "build-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    checksum_lines = []
    for relative in sorted([*files, "release/build-manifest.json"]):
        digest = hashlib.sha256((args.output / relative).read_bytes()).hexdigest()
        checksum_lines.append(f"{digest}  {relative}")
    checksums_path = args.output / "release" / "checksums.sha256"
    checksums_path.write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")

    total_rows = sum(entry["row_count"] for entry in files.values())
    print(f"Assembled {args.output} ({len(files)} file(s), {total_rows} row(s) total).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

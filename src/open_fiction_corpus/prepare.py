"""Fetch, extract, clean, and modernise one work's source text.

`prepare_work` writes the canonical cleaned text to workspace/clean/<work-id>.txt,
reproducible from the pinned raw source plus the versioned extractor, cleaner,
and moderniser named in the manifest and the work-specific overrides file.
"""

from __future__ import annotations

import hashlib
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

import yaml

# One request per work per invocation, no automatic retries, no crawling;
# see the source access policy in docs/cleaning-guide.md.
_USER_AGENT = "open-fiction-corpus (+https://github.com/open-fiction-corpus/open-fiction-corpus)"

# Approved https download origins per provider. Manifests are contributor
# input, so the fetcher only ever contacts these hosts; adding one (e.g. an
# official Gutenberg mirror) is a reviewed code change under the source
# access policy.
APPROVED_SOURCE_HOSTS: dict[str, frozenset[str]] = {
    "gutenberg": frozenset({"www.gutenberg.org", "gutenberg.org"}),
}

_MAX_DOWNLOAD_BYTES = 64 * 1024 * 1024

_FORMAT_EXTENSIONS = {"txt": "txt", "xhtml": "xhtml", "html": "html", "epub": "epub", "markdown": "md"}


def is_approved_download_url(url: str, hosts: frozenset[str]) -> bool:
    """True only for https URLs on an approved host at the default port 443.

    The single authority for origin approval: validation, the initial fetch,
    and every redirect all use this check, so they cannot drift apart.
    """
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        return False
    return parts.scheme == "https" and parts.hostname in hosts and port in (None, 443)


class _ApprovedRedirects(urllib.request.HTTPRedirectHandler):
    """Follow redirects only to approved https origins."""

    def __init__(self, hosts: frozenset[str]) -> None:
        self.hosts = hosts

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not is_approved_download_url(newurl, self.hosts):
            raise ValueError(f"Refusing redirect to unapproved location: {newurl}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = yaml.safe_load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: top-level value must be a mapping")
    return value


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def raw_source_path(root: Path, manifest: dict[str, Any]) -> Path:
    """The canonical location of a work's fetched raw artifact."""
    extension = _FORMAT_EXTENSIONS[manifest["source"]["format"]]
    return root / "workspace" / "raw" / manifest["id"] / f"{manifest['id']}.{extension}"


def _download(url: str, hosts: frozenset[str]) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    opener = urllib.request.build_opener(_ApprovedRedirects(hosts))
    try:
        with opener.open(request, timeout=60) as response:
            data = response.read(_MAX_DOWNLOAD_BYTES + 1)
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Failed to fetch {url}: {exc}") from exc
    if len(data) > _MAX_DOWNLOAD_BYTES:
        raise ValueError(f"{url} exceeds the {_MAX_DOWNLOAD_BYTES}-byte download limit")
    return data


def fetch_source(root: Path, manifest: dict[str, Any]) -> Path:
    """Download the exact artifact named by source.download_url and verify its hash.

    Manifests are contributor input: the fetcher only contacts approved
    provider origins, refuses redirects elsewhere, caps the response size,
    and stores the artifact under a project-controlled filename derived from
    the work id — the remote basename is never used. The file is written
    only after the hash check passes, so a failed verification leaves
    nothing behind for a later --skip-fetch run to trust.
    """
    source = manifest["source"]
    provider = source["provider"]
    hosts = APPROVED_SOURCE_HOSTS.get(provider)
    if hosts is None:
        raise ValueError(f"No fetcher for source provider '{provider}'")
    url = source.get("download_url")
    if not url:
        raise ValueError(
            f"{manifest['id']}: source.download_url must name the exact artifact to fetch"
        )
    if not is_approved_download_url(url, hosts):
        raise ValueError(
            f"{manifest['id']}: source.download_url must use https on an approved "
            f"'{provider}' host {sorted(hosts)} on port 443: {url}"
        )

    data = _download(url, hosts)
    digest = _sha256(data)
    pinned = manifest.get("processing", {}).get("source_sha256")
    if pinned is not None and digest != pinned:
        raise ValueError(
            f"{manifest['id']}: source hash mismatch: expected {pinned}, got {digest}; "
            "nothing was written"
        )

    raw_path = raw_source_path(root, manifest)
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = raw_path.with_name(raw_path.name + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(raw_path)

    if pinned is None:
        print(f"Fetched {url}")
        print(f"Unpinned source; record processing.source_sha256: {digest}")
    else:
        print(f"Fetched {url} (sha256 verified)")
    return raw_path


_GUTENBERG_CREDIT = re.compile(
    r"^\s*(produced by|e-?text prepared by|transcribed (by|from)|special thanks)", re.IGNORECASE
)


def extract_gutenberg_txt(raw_text: str) -> str:
    """Return the body between the Project Gutenberg start and end markers."""
    lines = raw_text.split("\n")
    starts = [i for i, line in enumerate(lines) if line.startswith("*** START OF")]
    ends = [i for i, line in enumerate(lines) if line.startswith("*** END OF")]
    if len(starts) != 1 or len(ends) != 1 or starts[0] >= ends[0]:
        raise ValueError(
            "Expected exactly one Project Gutenberg '*** START OF' marker "
            "followed by one '*** END OF' marker"
        )
    body = "\n".join(lines[starts[0] + 1 : ends[0]]).strip("\n")

    # Drop leading transcriber-credit paragraphs without reflowing anything
    # else, so blank-line structure survives for the cleaner to interpret.
    while _GUTENBERG_CREDIT.match(body):
        gap = re.search(r"\n{2,}", body)
        if gap is None:
            return ""
        body = body[gap.end() :]
    return body


def clean_fiction(text: str) -> str:
    """Normalise whitespace and unwrap hard-wrapped prose paragraphs.

    Paragraph breaks become one blank line; larger gaps (section breaks in the
    transcription) are preserved as two blank lines. Emphasis markup, headings,
    spelling, and punctuation are left untouched.

    Scope: prose-only. Unwrapping flattens intentional lineation, so works
    containing verse, songs, or other lineated material need a future cleaner
    version; see the cleaning guide.
    """
    text = text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    parts = re.split(r"(\n{2,})", text.strip("\n"))
    pieces: list[str] = []
    for part in parts:
        if part.startswith("\n"):
            pieces.append("\n\n" if part == "\n\n" else "\n\n\n")
        else:
            joined = " ".join(line.strip() for line in part.split("\n"))
            pieces.append(re.sub(r"[ \t]{2,}", " ", joined).strip())
    return "".join(pieces).strip() + "\n"


def _match_case(replacement: str, matched: str) -> str:
    if matched.isupper() and len(matched) > 1:
        return replacement.upper()
    if matched[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def modernize_spelling(text: str, root: Path) -> tuple[str, dict[str, int]]:
    """Apply the whole-word spelling rules from schema/modernization-rules.yaml.

    Replacements are case-preserving and reported per rule so every change is
    auditable. Grammar, vocabulary, dialect, and punctuation are never touched.
    """
    rules_path = root / "schema" / "modernization-rules.yaml"
    rules = _load_yaml(rules_path).get("rules", {})
    counts: dict[str, int] = {}
    for old, new in rules.items():
        if not isinstance(old, str) or not isinstance(new, str):
            raise ValueError(f"{rules_path}: rules must map strings to strings")
        pattern = re.compile(rf"\b{re.escape(old)}\b", re.IGNORECASE)
        text, count = pattern.subn(lambda match: _match_case(new, match.group(0)), text)
        if count:
            counts[old] = count
    return text, counts


def apply_overrides(text: str, overrides_path: Path) -> str:
    """Apply work-specific corrections, each with a note and an exact match count."""
    corrections = _load_yaml(overrides_path).get("corrections", [])
    for index, correction in enumerate(corrections):
        find = correction.get("find")
        replace = correction.get("replace")
        note = correction.get("note")
        count = correction.get("count")
        if (
            not isinstance(find, str)
            or not find
            or not isinstance(replace, str)
            or not isinstance(note, str)
            or not note
            or isinstance(count, bool)
            or not isinstance(count, int)
            or count < 1
        ):
            raise ValueError(
                f"{overrides_path}: correction {index} needs a non-empty 'find', "
                "a 'replace', a 'note', and a positive integer 'count'"
            )
        occurrences = text.count(find)
        if occurrences != count:
            raise ValueError(
                f"{overrides_path}: correction {find!r} matched {occurrences} "
                f"time(s), expected {count}"
            )
        text = text.replace(find, replace)
    return text


EXTRACTORS: dict[str, Callable[[str], str]] = {
    "gutenberg_txt_v1": extract_gutenberg_txt,
}

CLEANERS: dict[str, Callable[[str], str]] = {
    "fiction_clean_v1": clean_fiction,
}

MODERNIZERS: dict[str, Callable[[str, Path], tuple[str, dict[str, int]]]] = {
    "modernize_spelling_v1": modernize_spelling,
}


def _lookup(registry: dict[str, Any], name: str, kind: str) -> Any:
    if name not in registry:
        raise ValueError(f"Unknown {kind} '{name}'; known: {sorted(registry)}")
    return registry[name]


def prepare_work(root: Path, work_id: str, *, skip_fetch: bool = False) -> Path:
    root = root.resolve()
    manifest_path = root / "catalog" / "works" / f"{work_id}.yaml"
    if not manifest_path.exists():
        raise FileNotFoundError(f"No manifest at {manifest_path}")
    manifest = _load_yaml(manifest_path)
    processing = manifest["processing"]

    if skip_fetch:
        # Only the canonical raw artifact qualifies: temporary files from an
        # interrupted fetch or strays from older pipeline versions never do.
        raw_path = raw_source_path(root, manifest)
        if not raw_path.is_file():
            raise FileNotFoundError(
                f"--skip-fetch requires the fetched raw file at {raw_path}"
            )
        pinned = processing.get("source_sha256")
        if pinned is not None:
            digest = _sha256(raw_path.read_bytes())
            if digest != pinned:
                raise ValueError(
                    f"{work_id}: raw file {raw_path.name} hash mismatch: "
                    f"expected {pinned}, got {digest}"
                )
    else:
        raw_path = fetch_source(root, manifest)

    raw_text = raw_path.read_text(encoding="utf-8")
    extractor = _lookup(EXTRACTORS, processing["extractor"], "extractor")
    cleaner = _lookup(CLEANERS, processing["cleaner"], "cleaner")
    text = cleaner(extractor(raw_text))

    modernizer_name = processing.get("modernizer")
    if modernizer_name:
        modernizer = _lookup(MODERNIZERS, modernizer_name, "modernizer")
        text, counts = modernizer(text, root)
        for old, count in sorted(counts.items()):
            print(f"Modernised {old!r}: {count} replacement(s)")

    overrides_path = root / "overrides" / f"{work_id}.yaml"
    if overrides_path.exists():
        text = apply_overrides(text, overrides_path)
        print(f"Applied overrides from {overrides_path}")

    words = len(text.split())
    minimum = processing.get("expected_min_words")
    if minimum and words < minimum:
        print(f"Warning: {words} words is below expected_min_words {minimum}")

    clean_dir = root / "workspace" / "clean"
    clean_dir.mkdir(parents=True, exist_ok=True)
    clean_path = clean_dir / f"{work_id}.txt"
    # Atomic replace: an interrupted run can never leave a truncated build
    # input behind, and any previously valid clean file survives until the
    # new one is fully written.
    temporary = clean_path.with_name(clean_path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(clean_path)
    print(f"Prepared {work_id}: {words} words -> {clean_path}")
    return clean_path

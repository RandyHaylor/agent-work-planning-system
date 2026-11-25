import os
import re
from typing import List, Dict, Any
from fastReader.cache import load_manifest
from fastReader.models import Document

CONTAINER_TYPES = ["chapter", "section", "subsection"]


def find_containers(line_number: int, manifest) -> Dict[str, Any]:
    """Walk backwards through markers to find the containing chapter/section/subsection."""
    containers = {}
    for m_type in CONTAINER_TYPES:
        markers = sorted(manifest.markers.get(m_type, []), key=lambda m: m.line)
        containing = None
        for m in markers:
            if m.line <= line_number:
                containing = m
            else:
                break
        if containing:
            containers[m_type] = {
                "index": containing.index,
                "line_number": containing.line,
                "preview": ""  # filled in below with document lines
            }
    return containers


def build_pattern(keywords: List[str], exact: bool, case_sensitive: bool) -> re.Pattern:
    parts = []
    for kw in keywords:
        escaped = re.escape(kw)
        if exact:
            escaped = rf"\b{escaped}\b"
        parts.append(escaped)
    combined = "|".join(parts)
    flags = 0 if case_sensitive else re.IGNORECASE
    return re.compile(combined, flags)


def _search_one(
    manifest_hash: str,
    cache_dir: str,
    keywords: List[str],
    exact: bool,
    case_sensitive: bool,
    match_all: bool,
    preview_length: int,
) -> List[Dict[str, Any]]:
    """Search a single manifest and return a list of hit dicts."""
    manifest_path = os.path.join(cache_dir, f"{manifest_hash}.json")
    content_path = os.path.join(cache_dir, f"{manifest_hash}.txt")

    if not os.path.exists(manifest_path):
        raise FileNotFoundError(f"Manifest not found for hash: {manifest_hash}")
    if not os.path.exists(content_path):
        raise FileNotFoundError(f"Content not found for hash: {manifest_hash}")

    manifest = load_manifest(manifest_path)
    document = Document.from_file(content_path)

    if match_all:
        patterns = [build_pattern([kw], exact, case_sensitive) for kw in keywords]
    else:
        patterns = [build_pattern(keywords, exact, case_sensitive)]

    hits = []
    for line_idx, line in enumerate(document.lines):
        line_number = line_idx + 1
        if match_all:
            if not all(p.search(line) for p in patterns):
                continue
        else:
            if not patterns[0].search(line):
                continue

        preview = line.strip()[:preview_length]
        containers = find_containers(line_number, manifest)
        for m_type, info in containers.items():
            container_line = document.lines[info["line_number"] - 1]
            info["preview"] = container_line.strip()[:50]

        hits.append({
            "line_number": line_number,
            "preview": preview,
            "containers": containers,
        })

    return hits


def run_search(
    manifest_hashes: List[str],
    cache_dir: str,
    keywords: List[str],
    exact: bool = False,
    case_sensitive: bool = False,
    match_all: bool = False,
    preview_length: int = 80,
) -> Dict[str, List[Dict[str, Any]]]:
    """Search across one or more manifests. Returns results grouped by 'hash (source)'."""
    results = {}
    for manifest_hash in manifest_hashes:
        manifest_path = os.path.join(cache_dir, f"{manifest_hash}.json")
        if not os.path.exists(manifest_path):
            raise FileNotFoundError(f"Manifest not found for hash: {manifest_hash}")

        manifest = load_manifest(manifest_path)
        source = os.path.basename(manifest.source)
        key = f"{manifest_hash} ({source})"

        hits = _search_one(
            manifest_hash, cache_dir, keywords,
            exact, case_sensitive, match_all, preview_length
        )
        results[key] = hits

    return results

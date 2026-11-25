"""Local file implementation of ReaderCachePort (the original fastReader cache:
<8-char hash>.txt / .json under a cache directory). Used by the copied tests and local runs."""
import hashlib
import json
import os
from typing import Mapping, Union

from planning_system.fastreader.manifest_codec import manifest_from_dict, manifest_to_dict
from planning_system.fastreader.models import Manifest
from planning_system.fastreader.reader_cache_port import CachedItem, ReaderCachePort, ReaderCitation


def generate_hash(content: str) -> str:
    """Generate an 8-char mini-hash (SHA-256 prefix) of the content."""
    return hashlib.sha256(content.encode('utf-8')).hexdigest()[:8]


def save_text_to_cache(content: str, cache_dir: str) -> str:
    """Save content to cache directory as <hash>.txt."""
    os.makedirs(cache_dir, exist_ok=True)
    file_path = os.path.join(cache_dir, f"{generate_hash(content)}.txt")
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    return file_path


def save_manifest(manifest: Manifest, cache_dir: str, content_hash: str) -> str:
    """Save manifest to cache directory as <hash>.json."""
    os.makedirs(cache_dir, exist_ok=True)
    file_path = os.path.join(cache_dir, f"{content_hash}.json")
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(manifest_to_dict(manifest), f, indent=2)
    return file_path


def load_manifest(manifest_path: str) -> Manifest:
    """Load manifest from path and reconstruct Marker objects."""
    with open(manifest_path, 'r', encoding='utf-8') as f:
        return manifest_from_dict(json.load(f))


class FileReaderCache(ReaderCachePort):
    def __init__(self, cache_dir: str):
        self.cache_dir = cache_dir

    def save(self, text, manifest, source_label, metadata) -> str:
        content_hash = generate_hash(text)
        save_text_to_cache(text, self.cache_dir)
        save_manifest(manifest, self.cache_dir, content_hash)
        return content_hash

    def get(self, item_id) -> CachedItem:
        manifest_path = os.path.join(self.cache_dir, f"{item_id}.json")
        content_path = os.path.join(self.cache_dir, f"{item_id}.txt")
        if not os.path.exists(manifest_path):
            raise FileNotFoundError(f"Manifest not found for hash: {item_id}")
        if not os.path.exists(content_path):
            raise FileNotFoundError(f"Content not found for hash: {item_id}")
        manifest = load_manifest(manifest_path)
        with open(content_path, 'r', encoding='utf-8') as f:
            text = f.read()
        return CachedItem(item_id, manifest.source, text, manifest, {})

    def cite(self, item_id, start_line, end_line) -> ReaderCitation:
        raise NotImplementedError("the local file cache has no reference library; cite runs on the server")


def as_reader_cache(cache: Union[ReaderCachePort, str]) -> ReaderCachePort:
    """Commands accept a port, or a cache directory (the original signature) wrapped in FileReaderCache."""
    return FileReaderCache(cache) if isinstance(cache, str) else cache

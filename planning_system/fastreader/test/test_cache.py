import os
import shutil
import tempfile
import json
import pytest
from fastReader.cache import (
    generate_hash, 
    save_text_to_cache, 
    save_manifest, 
    load_manifest
)
from fastReader.models import Manifest, Marker

def test_generate_hash_consistency():
    """T15: generate_hash(content) returns consistent 8-char mini-hash for same content."""
    content = "Hello world"
    h1 = generate_hash(content)
    h2 = generate_hash(content)
    assert h1 == h2
    assert len(h1) == 8  # 8-char SHA-256 prefix

def test_generate_hash_different_content():
    """T16: generate_hash(content) returns different hash for different content."""
    assert generate_hash("a") != generate_hash("b")

def test_save_text_to_cache():
    """T17: save_text_to_cache(content, cache_dir) writes <hash>.txt and returns path."""
    temp_dir = tempfile.mkdtemp()
    try:
        content = "Sample document content"
        h = generate_hash(content)
        path = save_text_to_cache(content, temp_dir)
        
        assert os.path.exists(path)
        assert os.path.basename(path) == f"{h}.txt"
        with open(path, 'r') as f:
            assert f.read() == content
    finally:
        shutil.rmtree(temp_dir)

def test_save_text_to_cache_idempotency():
    """T18: save_text_to_cache is idempotent — same content, same path returned."""
    temp_dir = tempfile.mkdtemp()
    try:
        content = "Sample document content"
        path1 = save_text_to_cache(content, temp_dir)
        path2 = save_text_to_cache(content, temp_dir)
        assert path1 == path2
    finally:
        shutil.rmtree(temp_dir)

def test_save_manifest():
    """T19: save_manifest(manifest, cache_dir) writes <hash>.json and returns path."""
    temp_dir = tempfile.mkdtemp()
    try:
        markers = {"chapter": [Marker("chapter", 1, 1, 0)]}
        manifest = Manifest("source.txt", 100, 5, markers)
        # Hash should be based on something stable, let's say the source and total_chars for now
        # Actually, the plan implies <hash>.json usually matches the content hash if it's for that content.
        # Let's assume we pass the hash or use content hash.
        # For simplicity, let's use the source content hash if available, or just a hash of the manifest data.
        content_hash = generate_hash("content")
        path = save_manifest(manifest, temp_dir, content_hash)
        
        assert os.path.exists(path)
        assert os.path.basename(path) == f"{content_hash}.json"
    finally:
        shutil.rmtree(temp_dir)

def test_load_manifest():
    """T20: load_manifest(manifest_path) reconstructs correct Manifest with Marker objects."""
    temp_dir = tempfile.mkdtemp()
    try:
        markers = {"chapter": [Marker("chapter", 1, 10, 5)]}
        manifest = Manifest("test.md", 500, 20, markers)
        h = "fakehash"
        path = save_manifest(manifest, temp_dir, h)
        
        loaded = load_manifest(path)
        assert isinstance(loaded, Manifest)
        assert loaded.source == "test.md"
        assert loaded.total_chars == 500
        assert "chapter" in loaded.markers
        assert isinstance(loaded.markers["chapter"][0], Marker)
        assert loaded.markers["chapter"][0].line == 10
        assert loaded.markers["chapter"][0].char_index == 5
    finally:
        shutil.rmtree(temp_dir)

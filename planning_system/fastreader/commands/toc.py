import os
from typing import List, Dict, Any, Optional
from fastReader.cache import load_manifest
from fastReader.models import Document
from fastReader.toc_cli import build_toc

def run_toc(
    manifest_hash: str,
    cache_dir: str,
    marker_types: Optional[List[str]] = None,
    preview_length: int = 30,
    limit: Optional[int] = 15,
    end_preview_length: int = 0,
) -> List[Dict[str, Any]]:
    """Execute the toc command logic.
    
    1. Load manifest from <hash>.json
    2. Load content lines from <hash>.txt
    3. Build and return TOC
    """
    manifest_path = os.path.join(cache_dir, f"{manifest_hash}.json")
    content_path = os.path.join(cache_dir, f"{manifest_hash}.txt")
    
    if not os.path.exists(manifest_path):
        raise FileNotFoundError(f"Manifest not found for hash: {manifest_hash}")
    
    if not os.path.exists(content_path):
        raise FileNotFoundError(f"Content not found for hash: {manifest_hash}")
        
    manifest = load_manifest(manifest_path)
    document = Document.from_file(content_path)
    
    return build_toc(
        manifest,
        document.lines,
        marker_types=marker_types,
        preview_length=preview_length,
        limit=limit,
        end_preview_length=end_preview_length,
    )

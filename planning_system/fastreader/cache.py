import hashlib
import os
import json
from dataclasses import asdict
from typing import Dict, List
from fastReader.models import Manifest, Marker

def generate_hash(content: str) -> str:
    """Generate an 8-char mini-hash (SHA-256 prefix) of the content."""
    return hashlib.sha256(content.encode('utf-8')).hexdigest()[:8]

def save_text_to_cache(content: str, cache_dir: str) -> str:
    """Save content to cache directory as <hash>.txt."""
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir, exist_ok=True)
    
    content_hash = generate_hash(content)
    file_path = os.path.join(cache_dir, f"{content_hash}.txt")
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return file_path

def save_manifest(manifest: Manifest, cache_dir: str, content_hash: str) -> str:
    """Save manifest to cache directory as <hash>.json."""
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir, exist_ok=True)
    
    file_path = os.path.join(cache_dir, f"{content_hash}.json")
    
    # Convert dataclass to dict for JSON serialization
    manifest_dict = asdict(manifest)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(manifest_dict, f, indent=2)
    
    return file_path

def load_manifest(manifest_path: str) -> Manifest:
    """Load manifest from path and reconstruct Marker objects."""
    with open(manifest_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Reconstruct markers as Marker objects
    markers: Dict[str, List[Marker]] = {}
    for m_type, m_list in data['markers'].items():
        markers[m_type] = [Marker(**m_data) for m_data in m_list]
    
    return Manifest(
        source=data['source'],
        total_chars=data['total_chars'],
        total_lines=data['total_lines'],
        markers=markers
    )

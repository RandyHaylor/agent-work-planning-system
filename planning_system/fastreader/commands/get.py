import os
from typing import Optional
from fastReader.cache import load_manifest
from fastReader.models import Document, Marker

def run_get(
    manifest_hash: str,
    cache_dir: str,
    chapter: Optional[int] = None,
    section: Optional[int] = None,
    subsection: Optional[int] = None,
    page: Optional[int] = None,
    block: Optional[int] = None
) -> str:
    """Execute the get command logic.
    
    Returns the content requested by a specific marker.
    """
    manifest_path = os.path.join(cache_dir, f"{manifest_hash}.json")
    content_path = os.path.join(cache_dir, f"{manifest_hash}.txt")
    
    if not os.path.exists(manifest_path):
        raise FileNotFoundError(f"Manifest not found for hash: {manifest_hash}")
    
    manifest = load_manifest(manifest_path)
    document = Document.from_file(content_path)
    
    # 1. Find the target marker
    target_marker = None
    m_type = ""
    if chapter is not None:
        m_type = "chapter"
        target_marker = next((m for m in manifest.markers.get(m_type, []) if m.index == chapter), None)
    elif section is not None:
        m_type = "section"
        target_marker = next((m for m in manifest.markers.get(m_type, []) if m.index == section), None)
    elif subsection is not None:
        m_type = "subsection"
        target_marker = next((m for m in manifest.markers.get(m_type, []) if m.index == subsection), None)
    elif page is not None:
        m_type = "page_break"
        target_marker = next((m for m in manifest.markers.get(m_type, []) if m.index == page), None)
    elif block is not None:
        m_type = "block"
        target_marker = next((m for m in manifest.markers.get(m_type, []) if m.index == block), None)
        
    if not target_marker:
        idx = chapter or section or subsection or page or block
        return f"Error: {m_type} {idx} not found."
        
    # 2. Find the "next" marker of the SAME OR HIGHER level to determine boundary
    # Level hierarchy: chapter > section > page > block
    levels = ["chapter", "section", "subsection", "page_break", "page", "double_line_break", "block"]
    target_level_idx = levels.index(m_type)
    relevant_levels = levels[:target_level_idx + 1]
    
    all_markers = []
    for level in relevant_levels:
        all_markers.extend(manifest.markers.get(level, []))
        
    all_markers.sort(key=lambda m: m.line)
    
    # Start line
    start_line_idx = target_marker.line - 1
    
    # End line
    next_marker = next((m for m in all_markers if m.line > target_marker.line), None)
    if next_marker:
        end_line_idx = next_marker.line - 1
    else:
        end_line_idx = len(document.lines)
        
    return "\n".join(document.lines[start_line_idx:end_line_idx])

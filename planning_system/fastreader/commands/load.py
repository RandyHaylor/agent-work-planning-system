import os
from typing import Dict, Any, List
from fastReader.models import Document, Manifest
from fastReader.scanner import scan_document
from fastReader.cache import generate_hash, save_text_to_cache, save_manifest
from fastReader.toc_cli import build_toc

def run_load(file_path: str, cache_dir: str, config: Dict[str, Any], slice_starting_line: int = None, slice_line_count: int = None) -> Dict[str, Any]:
    """Execute the load command logic.

    If slice_starting_line and slice_line_count are provided, only those lines
    from the source are ingested. The slice is hashed on its own content so
    it gets a distinct manifest hash — the agent can drill into a meaty
    section by loading just its line range and then running toc/get/search
    against that smaller slice without touching the parent document.

    1. Read file from file_path
    2. Optionally slice by line range
    3. Save content to cache as <hash>.txt
    4. Scan document to create Manifest
    5. Save Manifest to cache as <hash>.json
    6. Return manifest_id and count summary
    """
    # 1. Read file content
    with open(file_path, 'r', encoding='utf-8') as f:
        file_content = f.read()

    # 2. Optional slice — carves out lines [START .. START+COUNT-1] (1-based
    # START). Slice is the new "document" from here on; its hash is a fresh
    # content hash of just the sliced text.
    if slice_starting_line is not None and slice_line_count is not None:
        all_original_lines = file_content.split('\n')
        zero_based_slice_start = max(0, slice_starting_line - 1)
        zero_based_slice_end = min(len(all_original_lines), zero_based_slice_start + slice_line_count)
        sliced_lines_block = all_original_lines[zero_based_slice_start:zero_based_slice_end]
        file_content = '\n'.join(sliced_lines_block)

    # 2. Save content to cache
    content_hash = generate_hash(file_content)
    cache_path = save_text_to_cache(file_content, cache_dir)

    # 2. Scan document
    document = Document.from_file(cache_path)
    manifest = scan_document(document, config)
    manifest.source = file_path  # preserve original path, not cache path

    # 3. Save manifest
    save_manifest(manifest, cache_dir, content_hash)

    # 4. Build summary with marker counts
    summary = {
        "chapters": len(manifest.markers.get("chapter", [])),
        "sections": len(manifest.markers.get("section", [])),
        "subsections": len(manifest.markers.get("subsection", [])),
        "page_breaks": len(manifest.markers.get("page_break", [])),
        "pages": len(manifest.markers.get("page", [])),
        "double_line_breaks": len(manifest.markers.get("double_line_break", [])),
        "blocks": len(manifest.markers.get("block", []))
    }
    # Per-depth counts for the three universal structural scanners. Each
    # line in the summary becomes one printed "Label: N" entry in the CLI.
    for depth_marker_type_name in sorted(manifest.markers.keys()):
        if depth_marker_type_name.startswith('indent_depth_') \
                or depth_marker_type_name.startswith('bracket_depth_') \
                or depth_marker_type_name.startswith('tag_depth_'):
            count_for_this_marker_kind = len(manifest.markers[depth_marker_type_name])
            if count_for_this_marker_kind > 0:
                summary[depth_marker_type_name] = count_for_this_marker_kind

    return {
        "manifest_id": content_hash,
        "summary": summary
    }

from typing import Dict, Any, Mapping, Optional, Union
from planning_system.fastreader.models import Document
from planning_system.fastreader.scanner import scan_document
from planning_system.fastreader.cache import as_reader_cache
from planning_system.fastreader.reader_cache_port import ReaderCachePort


def run_load(file_path: str, cache: Union[ReaderCachePort, str], config: Dict[str, Any], slice_starting_line: int = None, slice_line_count: int = None) -> Dict[str, Any]:
    """Load a local file (the original entry point): read it, then run_load_text."""
    with open(file_path, 'r', encoding='utf-8') as f:
        file_content = f.read()
    return run_load_text(file_content, file_path, {}, cache, config,
                         slice_starting_line=slice_starting_line,
                         slice_line_count=slice_line_count)


def run_load_text(
    text: str,
    source_label: str,
    extraction_info: Mapping[str, Any],
    cache: Union[ReaderCachePort, str],
    config: Dict[str, Any],
    slice_starting_line: Optional[int] = None,
    slice_line_count: Optional[int] = None,
) -> Dict[str, Any]:
    """Execute the load command logic on text already in memory.

    If slice_starting_line and slice_line_count are provided, only those lines
    are ingested. The slice is stored on its own content so it gets a distinct
    id: the agent can drill into a big section by loading just its line range
    and then running toc/get/search against that smaller slice.

    extraction_info carries strategy_used / available_strategies (and other
    metadata) from the server's document extraction; string values are stored as metadata.
    """
    file_content = text
    if slice_starting_line is not None and slice_line_count is not None:
        all_original_lines = file_content.split('\n')
        zero_based_slice_start = max(0, slice_starting_line - 1)
        zero_based_slice_end = min(len(all_original_lines), zero_based_slice_start + slice_line_count)
        file_content = '\n'.join(all_original_lines[zero_based_slice_start:zero_based_slice_end])

    document = Document.from_text(source_label, file_content)
    manifest = scan_document(document, config)
    manifest.source = source_label

    metadata = {k: v for k, v in extraction_info.items() if isinstance(v, str)}
    cache_id = as_reader_cache(cache).save(file_content, manifest, source_label, metadata)

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
        "manifest_id": cache_id,
        "cache_id": cache_id,
        "summary": summary,
        "strategy_used": extraction_info.get("strategy_used"),
        "available_strategies": list(extraction_info.get("available_strategies", [])),
    }

from typing import List, Dict, Any, Optional
from fastReader.models import Manifest, Marker
from fastReader.preview import extract_preview

def build_toc(
    manifest: Manifest,
    content_lines: List[str],
    marker_types: List[str] = None,
    preview_length: int = 30,
    limit: Optional[int] = 15,
    end_preview_length: int = 0,
) -> List[Dict[str, Any]]:
    """Build a Table of Contents list of dicts.
    
    Args:
        manifest: The document manifest
        content_lines: List of document lines
        marker_types: List of marker types to include (default: ['section'])
        preview_length: Length of preview to extract
        limit: Maximum number of entries to return (default: 15)
        
    Returns:
        List of TOC entry dictionaries
    """
    if marker_types is None:
        marker_types = ['section']
        
    all_selected_markers: List[Marker] = []
    
    for m_type in marker_types:
        if m_type in manifest.markers:
            all_selected_markers.extend(manifest.markers[m_type])
            
    # Sort by line number (interleaving)
    all_selected_markers.sort(key=lambda m: m.line)
    
    # Apply limit
    if limit is not None:
        all_selected_markers = all_selected_markers[:limit]
        
    toc: List[Dict[str, Any]] = []
    for marker in all_selected_markers:
        preview = extract_preview(
            content_lines, 
            marker.line, 
            marker.char_index, 
            preview_length
        )
        
        end_preview_text = ''
        marker_line_span = getattr(marker, 'line_span', 0)
        if end_preview_length > 0 and marker_line_span > 0:
            end_preview_text = _extract_end_preview_from_span(
                content_lines, marker.line, marker_line_span, end_preview_length
            )

        toc.append({
            "type": marker.marker_type,
            "index": marker.index,
            "line_number": marker.line,
            "preview": preview,
            "children_count": getattr(marker, 'children_count', 0),
            "line_span": marker_line_span,
            "end_preview": end_preview_text,
        })

    return toc


def _extract_end_preview_from_span(
    content_lines: List[str],
    marker_start_line_one_based: int,
    marker_line_span: int,
    end_preview_char_count: int,
) -> str:
    """Take the last N characters of the text covered by a marker's line span.

    Useful for prose markers (chapter/section/subsection) where the closing
    sentences often carry the hypothesis/conclusion of the block. Blanks
    whitespace-only text, collapses trailing newlines.
    """
    if marker_line_span <= 0 or end_preview_char_count <= 0:
        return ''
    zero_based_start = max(0, marker_start_line_one_based - 1)
    zero_based_end_exclusive = min(len(content_lines), zero_based_start + marker_line_span)
    covered_lines = content_lines[zero_based_start:zero_based_end_exclusive]
    covered_text = '\n'.join(covered_lines).rstrip()
    if not covered_text:
        return ''
    return covered_text[-end_preview_char_count:]

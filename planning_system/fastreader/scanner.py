import json
import re
from typing import Dict, List
from fastReader.models import Document, Manifest, Marker


def load_config(config_path: str) -> dict:
    """Load configuration from a JSON file.

    Args:
        config_path: Path to the configuration JSON file

    Returns:
        Dictionary containing the configuration
    """
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def scan_document(document: Document, config: dict) -> Manifest:
    """Scan a document for structural markers using patterns from config.

    Args:
        document: Document object with path, content, and lines
        config: Configuration dictionary with marker patterns

    Returns:
        Manifest object with detected markers
    """
    markers: Dict[str, List[Marker]] = {
        "chapter": [],
        "section": [],
        "subsection": [],
        "page_break": [],
        "page": [],
        "double_line_break": [],
        "block": []
    }

    # Track indices for each marker type
    marker_indices: Dict[str, int] = {
        "chapter": 0,
        "section": 0,
        "subsection": 0,
        "page_break": 0,
        "page": 0,
        "double_line_break": 0,
        "block": 0
    }

    # Detect structural markers by scanning each line
    previous_blank = False
    blank_count = 0

    for line_num, line in enumerate(document.lines, start=1):
        # Calculate char_index (position of first non-whitespace char)
        stripped_line = line.lstrip()
        char_index = len(line) - len(stripped_line)

        # Check for double line breaks (2+ consecutive blank lines)
        if line.strip() == "":
            blank_count += 1
            if blank_count >= 2 and not previous_blank:
                marker_indices["double_line_break"] += 1
                markers["double_line_break"].append(
                    Marker(
                        marker_type="double_line_break",
                        index=marker_indices["double_line_break"],
                        line=line_num,
                        char_index=0
                    )
                )
                previous_blank = True
        else:
            blank_count = 0
            previous_blank = False

            # Check each marker type's patterns
            for marker_type in ["chapter", "section", "subsection", "page_break", "page"]:
                if marker_type not in config:
                    continue

                patterns = config[marker_type].get("patterns", [])
                for pattern in patterns:
                    if re.search(pattern, line):
                        marker_indices[marker_type] += 1
                        markers[marker_type].append(
                            Marker(
                                marker_type=marker_type,
                                index=marker_indices[marker_type],
                                line=line_num,
                                char_index=char_index
                            )
                        )
                        break  # Only match one pattern per line per marker type

    # Create block fallback chunks
    if "block" in config:
        block_size = config["block"].get("size", 800)
        _create_blocks(document, markers, marker_indices, block_size)

    # Indent-level descend transitions (universal structure cue: Python, YAML,
    # outline notes, pretty-printed JSON, stack traces, tree output, ...).
    _emit_indent_depth_transition_markers(document, markers)

    # Bracket-nesting descend transitions (JSON/JSONL, logs with embedded
    # JSON, minified data). Single pass, string-literal aware.
    _emit_bracket_depth_transition_markers(document, markers)

    # HTML / XML tag nesting. Regex-find all potential tags, stack-match by
    # name, drop unmatched. Remaining balanced opens carry their depth.
    _emit_tag_depth_transition_markers(document, markers)

    # Compute line_span for each marker — distance in lines to the next
    # same-kind marker or to end-of-file.
    _populate_line_span_for_markers(markers, document.total_lines)

    # Create manifest
    manifest = Manifest(
        source=document.path,
        total_chars=document.total_chars,
        total_lines=document.total_lines,
        markers=markers
    )

    return manifest


def _ensure_depth_marker_bucket(markers: Dict[str, List[Marker]], marker_type: str) -> None:
    if marker_type not in markers:
        markers[marker_type] = []


def _emit_indent_depth_transition_markers(document: Document, markers: Dict[str, List[Marker]]) -> None:
    """Emit an `indent_depth_N` marker at every line where indent depth
    DESCENDS (enters a deeper block) relative to the previous non-blank line.

    Each emitted marker's `children_count` is updated as we encounter deeper
    descends BELOW it, giving the agent a size-at-a-glance per block.
    """
    indent_width_stack: List[int] = []
    previous_non_blank_depth = 0
    per_depth_indices: Dict[int, int] = {}
    # Parallel stack of emitted markers aligned with indent_width_stack, so
    # we can increment the parent's children_count when a child is emitted.
    emitted_marker_stack: List[Marker] = []
    for one_based_line_number, original_line in enumerate(document.lines, start=1):
        stripped_line = original_line.lstrip()
        if stripped_line == "":
            continue
        leading_whitespace_width = len(original_line) - len(stripped_line)
        while indent_width_stack and indent_width_stack[-1] >= leading_whitespace_width:
            indent_width_stack.pop()
            if emitted_marker_stack:
                emitted_marker_stack.pop()
        indent_width_stack.append(leading_whitespace_width)
        current_indent_depth = len(indent_width_stack) - 1
        is_descend_transition = current_indent_depth > previous_non_blank_depth
        if is_descend_transition:
            depth_marker_type = f"indent_depth_{current_indent_depth}"
            _ensure_depth_marker_bucket(markers, depth_marker_type)
            per_depth_indices[current_indent_depth] = per_depth_indices.get(current_indent_depth, 0) + 1
            newly_emitted_marker = Marker(
                marker_type=depth_marker_type,
                index=per_depth_indices[current_indent_depth],
                line=one_based_line_number,
                char_index=leading_whitespace_width,
            )
            markers[depth_marker_type].append(newly_emitted_marker)
            if emitted_marker_stack:
                emitted_marker_stack[-1].children_count += 1
            emitted_marker_stack.append(newly_emitted_marker)
        else:
            # Same-depth sibling transition: not a descend, so no marker emitted,
            # but we still align emitted_marker_stack by popping to the level
            # of the current node's parent (done via the while-pop above).
            pass
        previous_non_blank_depth = current_indent_depth


def _emit_bracket_depth_transition_markers(document: Document, markers: Dict[str, List[Marker]]) -> None:
    """Emit `bracket_depth_N` markers for every balanced `{` or `[`.

    Same architecture as the HTML/XML tag scanner:
      1. COLLECT every bracket event into a flat list of dicts (kind,
         bracket_type, line, char_index). Best-effort string-literal skip
         per line (reset at newline so a bad line can't drift forever).
      2. MATCH via inside-out pruning: on each close, search the stack top
         -> bottom for an opener of the SAME bracket type (`}`→`{`, `]`→`[`).
         Mark the found opener balanced and discard everything above it.
      3. ASSIGN canonical depth by rewalking only balanced opens on a clean
         stack — depth at push time is the true nesting level.
    """
    bracket_event_list: List[Dict] = _collect_bracket_events(document.content)

    # MATCH: inside-out pruning stack match, respecting bracket type.
    BRACKET_CLOSER_TO_OPENER = {'}': '{', ']': '['}
    bracket_balance_stack: List[Dict] = []
    for bracket_event in bracket_event_list:
        if bracket_event['kind'] == 'open':
            bracket_balance_stack.append(bracket_event)
            continue
        required_opener_bracket_type = BRACKET_CLOSER_TO_OPENER[bracket_event['bracket_type']]
        matching_opener_stack_index = None
        for candidate_stack_index in range(len(bracket_balance_stack) - 1, -1, -1):
            if bracket_balance_stack[candidate_stack_index]['bracket_type'] == required_opener_bracket_type:
                matching_opener_stack_index = candidate_stack_index
                break
        if matching_opener_stack_index is not None:
            bracket_balance_stack[matching_opener_stack_index]['is_balanced'] = True
            bracket_balance_stack = bracket_balance_stack[:matching_opener_stack_index]

    # DEPTH: rewalk, clean stack, only balanced opens. Emit markers and
    # compute each marker's children_count by incrementing the parent
    # currently on top of the canonical stack each time a child is pushed.
    canonical_bracket_stack: List[Dict] = []
    canonical_emitted_marker_stack: List[Marker] = []
    per_depth_indices: Dict[int, int] = {}
    for bracket_event in bracket_event_list:
        if bracket_event['kind'] == 'open':
            if not bracket_event.get('is_balanced'):
                continue
            canonical_bracket_stack.append(bracket_event)
            canonical_bracket_depth = len(canonical_bracket_stack)
            depth_marker_type = f"bracket_depth_{canonical_bracket_depth}"
            _ensure_depth_marker_bucket(markers, depth_marker_type)
            per_depth_indices[canonical_bracket_depth] = per_depth_indices.get(canonical_bracket_depth, 0) + 1
            newly_emitted_marker = Marker(
                marker_type=depth_marker_type,
                index=per_depth_indices[canonical_bracket_depth],
                line=bracket_event['line'],
                char_index=bracket_event['char_index'],
            )
            markers[depth_marker_type].append(newly_emitted_marker)
            if canonical_emitted_marker_stack:
                canonical_emitted_marker_stack[-1].children_count += 1
            canonical_emitted_marker_stack.append(newly_emitted_marker)
        else:
            required_opener_bracket_type = BRACKET_CLOSER_TO_OPENER[bracket_event['bracket_type']]
            if canonical_bracket_stack and canonical_bracket_stack[-1]['bracket_type'] == required_opener_bracket_type:
                canonical_bracket_stack.pop()
                if canonical_emitted_marker_stack:
                    canonical_emitted_marker_stack.pop()


def _collect_bracket_events(source_content: str) -> List[Dict]:
    """Scan the raw text once, emit every `{`/`[`/`}`/`]` occurrence as an
    event dict. Best-effort skips brackets inside `"..."` string literals
    and resets string state on newline so a corrupted line cannot poison
    the rest of the file. In valid JSON/JSONL strings can't contain raw
    newlines anyway, so this reset is safe on well-formed input.
    """
    collected_bracket_events: List[Dict] = []
    currently_inside_string_literal = False
    previous_char_was_backslash_escape = False
    current_line_number = 1
    current_char_index_within_line = 0
    for one_char in source_content:
        if one_char == '\n':
            current_line_number += 1
            current_char_index_within_line = 0
            currently_inside_string_literal = False
            previous_char_was_backslash_escape = False
            continue
        if currently_inside_string_literal:
            if previous_char_was_backslash_escape:
                previous_char_was_backslash_escape = False
            elif one_char == '\\':
                previous_char_was_backslash_escape = True
            elif one_char == '"':
                currently_inside_string_literal = False
            current_char_index_within_line += 1
            continue
        if one_char == '"':
            currently_inside_string_literal = True
        elif one_char == '{' or one_char == '[':
            collected_bracket_events.append({
                'kind': 'open',
                'bracket_type': one_char,
                'line': current_line_number,
                'char_index': current_char_index_within_line,
                'is_balanced': False,
            })
        elif one_char == '}' or one_char == ']':
            collected_bracket_events.append({
                'kind': 'close',
                'bracket_type': one_char,
                'line': current_line_number,
                'char_index': current_char_index_within_line,
            })
        current_char_index_within_line += 1
    return collected_bracket_events


_HTML_XML_TAG_SCAN_PATTERN = re.compile(
    r'<(?P<closing_slash>/?)(?P<tag_name>[A-Za-z][A-Za-z0-9_:-]*)\b[^>]*?(?P<self_closing_slash>/?)>',
    re.DOTALL,
)
_HTML_XML_SKIP_CONSTRUCT_PATTERNS = [
    re.compile(r'<!--.*?-->', re.DOTALL),
    re.compile(r'<!\[CDATA\[.*?\]\]>', re.DOTALL),
    re.compile(r'<!DOCTYPE[^>]*>', re.IGNORECASE),
    re.compile(r'<\?.*?\?>', re.DOTALL),
]


def _emit_tag_depth_transition_markers(document: Document, markers: Dict[str, List[Marker]]) -> None:
    """Detect HTML/XML tag nesting and emit `tag_depth_N` markers for every
    balanced opening tag.

    Algorithm (per user spec):
      1. Mask out comments/CDATA/DOCTYPE/processing-instructions so their
         contents do not produce phantom tags.
      2. Regex-find all remaining `<tag ...>` and `</tag>` occurrences,
         building a flat list of tag objects with (kind, name, line, char).
         Self-closing tags (`<br/>`) are skipped — they do not change depth.
      3. Stack-match: push opens, on a close try to match top-of-stack by
         name. If matches, pop and mark the opener as balanced (stamp its
         post-push stack depth). If not, drop the close and move on.
      4. Leftover opens (never closed) are dropped.
      5. For each balanced open, emit a `tag_depth_N` marker where N is the
         stack depth recorded at push time.
    """
    raw_content = document.content
    # Blank out skip-regions (keep length identical so offsets stay aligned).
    masked_content = raw_content
    for skip_pattern in _HTML_XML_SKIP_CONSTRUCT_PATTERNS:
        def _replace_matched_region_with_equivalent_length_spaces(match_object):
            return ' ' * (match_object.end() - match_object.start())
        masked_content = skip_pattern.sub(_replace_matched_region_with_equivalent_length_spaces, masked_content)

    collected_tag_events: List[Dict] = []
    for tag_match in _HTML_XML_TAG_SCAN_PATTERN.finditer(masked_content):
        if tag_match.group('self_closing_slash') == '/':
            continue
        tag_start_offset = tag_match.start()
        line_number_for_this_tag = masked_content.count('\n', 0, tag_start_offset) + 1
        last_newline_before_tag = masked_content.rfind('\n', 0, tag_start_offset)
        char_index_within_line = tag_start_offset - (last_newline_before_tag + 1) if last_newline_before_tag >= 0 else tag_start_offset
        collected_tag_events.append({
            'kind': 'close' if tag_match.group('closing_slash') == '/' else 'open',
            'name': tag_match.group('tag_name').lower(),
            'line': line_number_for_this_tag,
            'char_index': char_index_within_line,
            'depth_at_push': None,
            'is_balanced': False,
        })

    # Pass A: prune-from-inside-out balance matching. On each close, search
    # the stack from top down for an opener with the same name. If found,
    # mark that opener balanced and discard everything above it as
    # unmatched. Unclosed inner tags (e.g. <meta>, <br>) get pruned so the
    # surrounding <head>, <body>, <html> still balance correctly.
    balance_matching_stack: List[Dict] = []
    for tag_event in collected_tag_events:
        if tag_event['kind'] == 'open':
            balance_matching_stack.append(tag_event)
            continue
        matching_opener_stack_index = None
        for candidate_stack_index in range(len(balance_matching_stack) - 1, -1, -1):
            if balance_matching_stack[candidate_stack_index]['name'] == tag_event['name']:
                matching_opener_stack_index = candidate_stack_index
                break
        if matching_opener_stack_index is not None:
            matched_opener_event = balance_matching_stack[matching_opener_stack_index]
            matched_opener_event['is_balanced'] = True
            # Drop the match and everything above it (those are unmatched opens).
            balance_matching_stack = balance_matching_stack[:matching_opener_stack_index]

    # Pass B: walk the tag-event list again with a CLEAN stack that only
    # pushes balanced opens and pops on their balanced closers. The stack
    # length AFTER each balanced push is the canonical tag depth. Each
    # parent's children_count ticks up when a balanced child is pushed
    # while the parent is still on the canonical stack.
    canonical_depth_stack: List[Dict] = []
    canonical_emitted_marker_stack: List[Marker] = []
    per_depth_indices: Dict[int, int] = {}
    for tag_event in collected_tag_events:
        if tag_event['kind'] == 'open':
            if not tag_event['is_balanced']:
                continue
            canonical_depth_stack.append(tag_event)
            canonical_tag_depth = len(canonical_depth_stack)
            depth_marker_type = f"tag_depth_{canonical_tag_depth}"
            _ensure_depth_marker_bucket(markers, depth_marker_type)
            per_depth_indices[canonical_tag_depth] = per_depth_indices.get(canonical_tag_depth, 0) + 1
            newly_emitted_marker = Marker(
                marker_type=depth_marker_type,
                index=per_depth_indices[canonical_tag_depth],
                line=tag_event['line'],
                char_index=tag_event['char_index'],
            )
            markers[depth_marker_type].append(newly_emitted_marker)
            if canonical_emitted_marker_stack:
                canonical_emitted_marker_stack[-1].children_count += 1
            canonical_emitted_marker_stack.append(newly_emitted_marker)
        else:
            if canonical_depth_stack and canonical_depth_stack[-1]['name'] == tag_event['name']:
                canonical_depth_stack.pop()
                if canonical_emitted_marker_stack:
                    canonical_emitted_marker_stack.pop()


def _create_blocks(document: Document, markers: Dict[str, List[Marker]],
                   marker_indices: Dict[str, int], block_size: int) -> None:
    """Create block fallback chunks in the document.

    Args:
        document: Document object
        markers: Dictionary to add block markers to
        marker_indices: Dictionary of marker indices
        block_size: Size of each block in characters
    """
    content = document.content
    offset = 0
    block_num = 0

    while offset < len(content):
        block_num += 1
        block_end = min(offset + block_size, len(content))

        # Find the line number where this block starts
        line_num = content[:offset].count('\n') + 1

        # Calculate char_index within that line
        last_newline = content.rfind('\n', 0, offset)
        if last_newline == -1:
            char_index = offset
        else:
            char_index = offset - (last_newline + 1)

        markers["block"].append(
            Marker(
                marker_type="block",
                index=block_num,
                line=line_num,
                char_index=char_index
            )
        )

        offset = block_end


def _populate_line_span_for_markers(markers: Dict[str, List[Marker]], document_total_line_count: int) -> None:
    """For each marker kind, sort by line and compute line_span = distance
    to the next same-kind marker, or to end-of-file for the last one.

    Gives a size-at-a-glance per section/chapter/subsection (prose), and
    is also meaningful for indent/bracket/tag markers as a secondary
    coverage hint.
    """
    for marker_kind_name, marker_list_for_this_kind in markers.items():
        if not marker_list_for_this_kind:
            continue
        markers_sorted_by_line = sorted(marker_list_for_this_kind, key=lambda each_marker: each_marker.line)
        for list_index, each_marker in enumerate(markers_sorted_by_line):
            is_last_same_kind_marker = list_index == len(markers_sorted_by_line) - 1
            if is_last_same_kind_marker:
                each_marker.line_span = max(0, document_total_line_count - each_marker.line + 1)
            else:
                next_same_kind_marker = markers_sorted_by_line[list_index + 1]
                each_marker.line_span = max(0, next_same_kind_marker.line - each_marker.line)

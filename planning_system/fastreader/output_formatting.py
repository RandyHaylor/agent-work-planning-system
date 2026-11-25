"""fastReader output formatting: JSON-able command results -> the text the CLI prints.

No execution, no cache. Reused by the thin `planning` CLI on server responses.
"""
import json
import os
from typing import Any, Dict, List, Mapping

AGENT_INSTRUCTIONS_PATH = os.path.join(os.path.dirname(__file__), "agent_instructions.json")

with open(AGENT_INSTRUCTIONS_PATH) as _f:
    _hints = json.load(_f)

HIGH_RISK_SPAN_VS_PREVIEW_RATIO_THRESHOLD = 10


def _strategy_lines(item: Mapping[str, Any]) -> List[str]:
    lines = []
    if item.get('strategy_used'):
        lines.append(f"  strategy used: {item['strategy_used']}")
        others = [s for s in item.get('available_strategies') or [] if s != item['strategy_used']]
        if others:
            lines.append(f"  other strategies: {', '.join(others)}")
    return lines


def format_load(loaded: List[Mapping[str, Any]]) -> str:
    """loaded: [{source, cache_id, summary, strategy_used?, available_strategies?}]."""
    out: List[str] = []
    if len(loaded) == 1:
        item = loaded[0]
        manifest_id = item['cache_id']
        out.append(f"\n{item['source']}")
        for key, count in item['summary'].items():
            if count > 0:
                out.append(f"  {key.replace('_', ' ').title()}: {count}")
        out.extend(_strategy_lines(item))
        out.append(f"\n  {_hints['after_load_single'][0].format(manifest_id=manifest_id)}")
        out.append(f"  {_hints['after_load_single'][1].format(manifest_id=manifest_id)}")
    else:
        out.append(f"\nLoaded {len(loaded)} files:")
        for item in loaded:
            name = os.path.basename(item['source'])
            counts = "  ".join(
                f"{k.split('_')[0]}:{v}"
                for k, v in item['summary'].items()
                if v > 0 and k in ('chapters', 'sections', 'subsections', 'blocks')
            )
            strategy = f"  strategy:{item['strategy_used']}" if item.get('strategy_used') else ""
            out.append(f"  {name:<40} hash:{item['cache_id']}  {counts}{strategy}")
        all_hashes = " ".join(item['cache_id'] for item in loaded)
        out.append(f"\n  {_hints['after_load_multi'][0]}")
        out.append(f"  {_hints['after_load_multi'][1].format(all_hashes=all_hashes)}")
    return "\n".join(out)


def format_inline_search(keywords: List[str], search_results: Dict[str, Any]) -> str:
    return f"\nSearch results for: {' '.join(keywords)}\n" + json.dumps(search_results, indent=2)


def format_toc(entries: List[Mapping[str, Any]], manifest_id: str, sample_size: int,
               end_sample_size: int, show_line_range_count: bool) -> str:
    out: List[str] = []
    largest_ratio = 0
    highest_ratio_entry_label = None
    highest_ratio_entry_span = 0
    for entry in entries:
        children_suffix = f"  ({entry['children_count']} children)" if entry.get('children_count', 0) > 0 else ""
        if show_line_range_count and entry.get('line_span', 0) > 0:
            range_start = entry['line_number']
            range_end = range_start + entry['line_span'] - 1
            line_location_display = f"ln {range_start}-{range_end} ({entry['line_span']})"
        else:
            line_location_display = f"ln {entry['line_number']}"
        out.append(f"{entry['type']} {entry['index']}  {line_location_display}  {entry['preview']}{children_suffix}")
        if end_sample_size > 0 and entry.get('end_preview'):
            out.append(f"    end: {entry['end_preview']}")
        entry_line_span = entry.get('line_span', 0)
        preview_budget = max(sample_size + end_sample_size, 1)
        if entry_line_span > 0:
            ratio = entry_line_span / preview_budget
            if ratio > largest_ratio:
                largest_ratio = ratio
                highest_ratio_entry_label = f"{entry['type']} {entry['index']}"
                highest_ratio_entry_span = entry_line_span
    out.append(f"\n# {_hints['after_toc'].format(manifest_id=manifest_id)}")
    out.append(f"# {_hints['after_toc_truncation_note']}")
    # A section ~10x larger than the combined start+end preview means the middle is invisible.
    if largest_ratio > HIGH_RISK_SPAN_VS_PREVIEW_RATIO_THRESHOLD and highest_ratio_entry_label:
        out.append(f"# {_hints['after_toc_truncation_warning_high_ratio'].format(section_label=highest_ratio_entry_label, span=highest_ratio_entry_span)}")
    return "\n".join(out)


def format_get(text: str) -> str:
    return text


def format_search(results: Mapping[str, List[Mapping[str, Any]]]) -> str:
    out: List[str] = []
    for key, hits in results.items():
        out.append(f"{key}: {len(hits)} hits")
        for hit in hits:
            containers = "  ".join(
                f"{t} {info['index']} ln {info['line_number']}  {info['preview']}"
                for t, info in hit['containers'].items()
            )
            out.append(f"  ln {hit['line_number']}  {hit['preview']}")
            if containers:
                out.append(f"    {containers}")
    return "\n".join(out)


def format_cite(citation: Mapping[str, Any]) -> str:
    return f"reference id {citation['item_id']}  lines {citation['start_line']}-{citation['end_line']}"


def format_error(message: str) -> str:
    return json.dumps({"error": message})

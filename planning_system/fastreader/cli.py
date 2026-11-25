import argparse
import sys
import json
import os
from typing import List, Optional
from fastReader.commands.load import run_load
from fastReader.commands.toc import run_toc
from fastReader.commands.get import run_get
from fastReader.commands.search import run_search
from fastReader.scanner import load_config

DEFAULT_CACHE_DIR = os.path.expanduser("~/.fastReader/cache")
DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
AGENT_INSTRUCTIONS_PATH = os.path.join(os.path.dirname(__file__), "agent_instructions.json")
HELP_CONTENT_JSON_PATH = os.path.join(os.path.dirname(__file__), "help_content.json")

with open(AGENT_INSTRUCTIONS_PATH) as _f:
    _hints = json.load(_f)

with open(HELP_CONTENT_JSON_PATH) as _help_content_file_handle:
    _help_content_by_subcommand = json.load(_help_content_file_handle)


def print_help_examples_for_subcommand(subcommand_name: str) -> None:
    subcommand_help_entry = _help_content_by_subcommand.get(subcommand_name, {})
    example_lines = subcommand_help_entry.get("examples", [])
    print(f"# Copy-paste examples for: fastReader.{subcommand_name}")
    print(f"# (replace <hash>, <h1>, <h2>, <file> with real values)")
    print()
    for one_line in example_lines:
        print(one_line)


def print_help_use_cases_for_subcommand(subcommand_name: str) -> None:
    subcommand_help_entry = _help_content_by_subcommand.get(subcommand_name, {})
    use_case_lines = subcommand_help_entry.get("use_cases", [])
    print(f"# Trigger -> command mapping for: fastReader.{subcommand_name}")
    print()
    for one_line in use_case_lines:
        print(one_line)

def parse_args(argv: List[str]) -> argparse.Namespace:
    """Parse command-line arguments for FastReader CLI."""
    parser = argparse.ArgumentParser(
        prog='llm-fast-reader',
        description='FastReader — Document Structure Layer for AI Agents'
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # 'load' subcommand
    load_parser = subparsers.add_parser('load', help='Scan a document file and create manifest')
    load_parser.add_argument('files', nargs='+', help='Path(s) to document file(s)')
    load_parser.add_argument('--search', nargs='+', metavar='KEYWORD', help='Search keywords to run immediately after loading')
    load_parser.add_argument('--exact', action='store_true', help='Whole-word search match')
    load_parser.add_argument('--case-sensitive', action='store_true', help='Case-sensitive search')
    load_parser.add_argument('--all', dest='match_all', action='store_true', help='All keywords must appear on the same line')
    load_parser.add_argument('--sample-size', type=int, default=80, help='Search result preview length (default: 80)')
    load_parser.add_argument('--line', type=int, nargs=2, metavar=('START', 'COUNT'), help='Slice source files: start at line START (1-based) and take COUNT lines. Creates a new manifest hash for each slice so the agent can drill into a big section recursively.')
    load_parser.add_argument('--help-examples', action='store_true', help='Print copy-paste recipes for load and exit')
    load_parser.add_argument('--help-use-cases', action='store_true', help='Print trigger -> command mapping for load and exit')

    # 'toc' subcommand
    toc_parser = subparsers.add_parser('toc', help='Display table of contents')
    toc_parser.add_argument('manifest', help='Manifest hash')
    toc_parser.add_argument('--chapters', action='store_true', help='Show chapters')
    toc_parser.add_argument('--sections', action='store_true', help='Show sections')
    toc_parser.add_argument('--subsections', action='store_true', help='Show subsections')
    toc_parser.add_argument('--pages', action='store_true', help='Show pages')
    toc_parser.add_argument('--blocks', action='store_true', help='Show blocks')
    toc_parser.add_argument('--indent-depth', type=int, metavar='N', help='Show indent-level descend transitions at depth N (Python, YAML, pretty JSON, outlines)')
    toc_parser.add_argument('--bracket-depth', type=int, metavar='N', help='Show JSON bracket-nesting descend transitions at depth N')
    toc_parser.add_argument('--tag-depth', type=int, metavar='N', help='Show HTML/XML balanced-tag depth N')
    toc_parser.add_argument('--sample-size', type=int, default=30, help='Preview length (default: 30)')
    toc_parser.add_argument('--limit', type=int, default=15, help='Limit number of entries (default: 15, use 0 for no limit)')
    toc_parser.add_argument('--show-line-range-count', action='store_true', help='Display "ln START-END (COUNT)" for each entry instead of just the start line')
    toc_parser.add_argument('--end-sample-size', type=int, default=0, help='Also show last N characters of each marker span (often the conclusion). 0 disables. Pairs with --sample-size which is the start preview.')
    toc_parser.add_argument('--help-examples', action='store_true', help='Print copy-paste recipes for toc and exit')
    toc_parser.add_argument('--help-use-cases', action='store_true', help='Print trigger -> command mapping for toc and exit')

    # 'get' subcommand
    get_parser = subparsers.add_parser('get', help='Retrieve content by reference')
    get_parser.add_argument('manifest', help='Manifest hash')
    get_parser.add_argument('--chapter', type=int, help='Chapter number')
    get_parser.add_argument('--section', type=int, help='Section number')
    get_parser.add_argument('--subsection', type=int, help='Subsection number')
    get_parser.add_argument('--page', type=int, help='Page number')
    get_parser.add_argument('--block', type=int, help='Block number')
    get_parser.add_argument('--help-examples', action='store_true', help='Print copy-paste recipes for get and exit')
    get_parser.add_argument('--help-use-cases', action='store_true', help='Print trigger -> command mapping for get and exit')

    # 'search' subcommand
    search_parser = subparsers.add_parser('search', help='Search for keywords and return hits with container context')
    search_parser.add_argument('keywords', nargs='+', help='Keywords to search for')
    search_parser.add_argument('--manifests', nargs='+', required=True, help='One or more manifest hashes to search')
    search_parser.add_argument('--exact', action='store_true', help='Match whole words only')
    search_parser.add_argument('--case-sensitive', action='store_true', help='Case-sensitive matching (default: case-insensitive)')
    search_parser.add_argument('--all', dest='match_all', action='store_true', help='All keywords must appear on the same line (default: any keyword matches)')
    search_parser.add_argument('--sample-size', type=int, default=80, help='Preview length per hit (default: 80)')
    search_parser.add_argument('--help-examples', action='store_true', help='Print copy-paste recipes for search and exit')
    search_parser.add_argument('--help-use-cases', action='store_true', help='Print trigger -> command mapping for search and exit')

    return parser.parse_args(argv)

VALID_SUBCOMMAND_NAMES = {'load', 'toc', 'get', 'search'}


def intercept_help_content_flags_before_argparse(argv: List[str]) -> bool:
    """Handle --help-examples and --help-use-cases before argparse parses the
    rest, because those flags should not require the subcommand's positional
    arguments (e.g. `toc --help-examples` shouldn't fail for missing hash).

    Returns True if a help-content flag was handled (main should return).
    """
    if not argv:
        return False
    subcommand_name_candidate = argv[0]
    if subcommand_name_candidate not in VALID_SUBCOMMAND_NAMES:
        return False
    if '--help-examples' in argv:
        print_help_examples_for_subcommand(subcommand_name_candidate)
        return True
    if '--help-use-cases' in argv:
        print_help_use_cases_for_subcommand(subcommand_name_candidate)
        return True
    return False


def main(argv: Optional[List[str]] = None):
    """Main entry point for FastReader CLI."""
    if argv is None:
        argv = sys.argv[1:]

    # Short-circuit on --help-examples / --help-use-cases BEFORE argparse,
    # so users can run e.g. `toc --help-examples` without supplying the
    # normally-required <hash> positional argument.
    if intercept_help_content_flags_before_argparse(argv):
        return

    args = parse_args(argv)

    if not os.path.exists(DEFAULT_CACHE_DIR):
        os.makedirs(DEFAULT_CACHE_DIR, exist_ok=True)
        
    config = load_config(DEFAULT_CONFIG_PATH)

    if args.command == 'load':
        loaded = []  # list of (file_path, manifest_id, summary) tuples

        slice_starting_line_or_none = args.line[0] if args.line else None
        slice_line_count_or_none = args.line[1] if args.line else None
        for file_path in args.files:
            try:
                result = run_load(file_path, DEFAULT_CACHE_DIR, config,
                                  slice_starting_line=slice_starting_line_or_none,
                                  slice_line_count=slice_line_count_or_none)
            except FileNotFoundError as e:
                print(f"Error: {e}", file=sys.stderr)
                continue
            loaded.append((file_path, result['manifest_id'], result['summary']))

        if len(loaded) == 1:
            # Single file — verbose output with browse/search hints
            file_path, manifest_id, summary = loaded[0]
            print(f"\n{file_path}")
            for key, count in summary.items():
                if count > 0:
                    label = key.replace('_', ' ').title()
                    print(f"  {label}: {count}")
            print(f"\n  {_hints['after_load_single'][0].format(manifest_id=manifest_id)}")
            print(f"  {_hints['after_load_single'][1].format(manifest_id=manifest_id)}")
        else:
            # Multi-file — compact combined table
            print(f"\nLoaded {len(loaded)} files:")
            for file_path, manifest_id, summary in loaded:
                name = os.path.basename(file_path)
                counts = "  ".join(
                    f"{k.split('_')[0]}:{v}"
                    for k, v in summary.items()
                    if v > 0 and k in ('chapters', 'sections', 'subsections', 'blocks')
                )
                print(f"  {name:<40} hash:{manifest_id}  {counts}")

            all_hashes = " ".join(m for _, m, _ in loaded)
            print(f"\n  {_hints['after_load_multi'][0]}")
            print(f"  {_hints['after_load_multi'][1].format(all_hashes=all_hashes)}")

        # Optional inline search
        if args.search and loaded:
            all_hashes_list = [m for _, m, _ in loaded]
            print(f"\nSearch results for: {' '.join(args.search)}")
            try:
                search_results = run_search(
                    all_hashes_list,
                    DEFAULT_CACHE_DIR,
                    keywords=args.search,
                    exact=args.exact,
                    case_sensitive=args.case_sensitive,
                    match_all=args.match_all,
                    preview_length=args.sample_size,
                )
                print(json.dumps(search_results, indent=2))
            except FileNotFoundError as e:
                print(f"Search error: {e}", file=sys.stderr)
        
    elif args.command == 'toc':
        marker_types = []
        if args.chapters: marker_types.append('chapter')
        if args.sections: marker_types.append('section')
        if args.subsections: marker_types.append('subsection')
        if args.pages: marker_types.append('page_break')
        if args.blocks: marker_types.append('block')
        if args.indent_depth is not None: marker_types.append(f'indent_depth_{args.indent_depth}')
        if args.bracket_depth is not None: marker_types.append(f'bracket_depth_{args.bracket_depth}')
        if args.tag_depth is not None: marker_types.append(f'tag_depth_{args.tag_depth}')

        if not marker_types:
            marker_types = ['section']
            
        limit = args.limit if args.limit > 0 else None
        
        try:
            result = run_toc(
                args.manifest,
                DEFAULT_CACHE_DIR,
                marker_types=marker_types,
                preview_length=args.sample_size,
                limit=limit,
                end_preview_length=args.end_sample_size,
            )
            largest_span_relative_to_preview_size_ratio = 0
            highest_ratio_entry_label = None
            highest_ratio_entry_span = 0
            for entry in result:
                children_suffix = f"  ({entry['children_count']} children)" if entry.get('children_count', 0) > 0 else ""
                if args.show_line_range_count and entry.get('line_span', 0) > 0:
                    range_start = entry['line_number']
                    range_end = range_start + entry['line_span'] - 1
                    line_location_display = f"ln {range_start}-{range_end} ({entry['line_span']})"
                else:
                    line_location_display = f"ln {entry['line_number']}"
                print(f"{entry['type']} {entry['index']}  {line_location_display}  {entry['preview']}{children_suffix}")
                if args.end_sample_size > 0 and entry.get('end_preview'):
                    print(f"    end: {entry['end_preview']}")
                # Track whether any entry is dangerously under-previewed (large span, tiny preview).
                entry_line_span = entry.get('line_span', 0)
                effective_combined_preview_char_budget = max(args.sample_size + args.end_sample_size, 1)
                if entry_line_span > 0:
                    current_entry_ratio = entry_line_span / effective_combined_preview_char_budget
                    if current_entry_ratio > largest_span_relative_to_preview_size_ratio:
                        largest_span_relative_to_preview_size_ratio = current_entry_ratio
                        highest_ratio_entry_label = f"{entry['type']} {entry['index']}"
                        highest_ratio_entry_span = entry_line_span
            print(f"\n# {_hints['after_toc'].format(manifest_id=args.manifest)}")
            print(f"# {_hints['after_toc_truncation_note']}")
            # High-risk warning threshold: a section ~10× larger than the
            # combined start+end preview means the middle is invisible.
            high_risk_span_vs_preview_ratio_threshold = 10
            if largest_span_relative_to_preview_size_ratio > high_risk_span_vs_preview_ratio_threshold and highest_ratio_entry_label:
                print(f"# {_hints['after_toc_truncation_warning_high_ratio'].format(section_label=highest_ratio_entry_label, span=highest_ratio_entry_span)}")
        except FileNotFoundError as e:
            print(json.dumps({"error": str(e)}), file=sys.stderr)
            sys.exit(1)

    elif args.command == 'get':
        try:
            result = run_get(
                args.manifest,
                DEFAULT_CACHE_DIR,
                chapter=args.chapter,
                section=args.section,
                subsection=args.subsection,
                page=args.page,
                block=args.block
            )
            print(result)
        except FileNotFoundError as e:
            print(json.dumps({"error": str(e)}), file=sys.stderr)
            sys.exit(1)
            
    elif args.command == 'search':
        try:
            results = run_search(
                args.manifests,
                DEFAULT_CACHE_DIR,
                keywords=args.keywords,
                exact=args.exact,
                case_sensitive=args.case_sensitive,
                match_all=args.match_all,
                preview_length=args.sample_size,
            )
            for key, hits in results.items():
                print(f"{key}: {len(hits)} hits")
                for hit in hits:
                    containers = "  ".join(
                        f"{t} {info['index']} ln {info['line_number']}  {info['preview']}"
                        for t, info in hit['containers'].items()
                    )
                    print(f"  ln {hit['line_number']}  {hit['preview']}")
                    if containers:
                        print(f"    {containers}")
        except FileNotFoundError as e:
            print(json.dumps({"error": str(e)}), file=sys.stderr)
            sys.exit(1)

    elif args.command is None:
        parse_args(['--help'])
    else:
        print(f"Command {args.command} not implemented yet.")

if __name__ == "__main__":
    main()

"""fastReader argument parsing and help-content flags. No execution, no cache.

Reused by the thin `planning` CLI so agents keep fastReader's command shape and help menus.
"""
import argparse
import json
import os
from typing import List

HELP_CONTENT_JSON_PATH = os.path.join(os.path.dirname(__file__), "help_content.json")

with open(HELP_CONTENT_JSON_PATH) as _help_content_file_handle:
    _help_content_by_subcommand = json.load(_help_content_file_handle)

VALID_SUBCOMMAND_NAMES = {'load', 'toc', 'get', 'search', 'cite'}


def help_examples_text(subcommand_name: str) -> str:
    example_lines = _help_content_by_subcommand.get(subcommand_name, {}).get("examples", [])
    return "\n".join([
        f"# Copy-paste examples for: planning_system.fastreader.{subcommand_name}",
        "# (replace <hash>, <h1>, <h2>, <file> with real values)",
        "",
        *example_lines,
    ])


def help_use_cases_text(subcommand_name: str) -> str:
    use_case_lines = _help_content_by_subcommand.get(subcommand_name, {}).get("use_cases", [])
    return "\n".join([
        f"# Trigger -> command mapping for: planning_system.fastreader.{subcommand_name}",
        "",
        *use_case_lines,
    ])


def print_help_examples_for_subcommand(subcommand_name: str) -> None:
    print(help_examples_text(subcommand_name))


def print_help_use_cases_for_subcommand(subcommand_name: str) -> None:
    print(help_use_cases_text(subcommand_name))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='llm-fast-reader',
        description='FastReader — Document Structure Layer for AI Agents'
    )
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    load_parser = subparsers.add_parser('load', help='Scan a document file and create manifest')
    load_parser.add_argument('files', nargs='+', help='Path(s) to document file(s)')
    load_parser.add_argument('--strategy', metavar='NAME', help='Extraction strategy to use (server picks one by default; see "other strategies" after load)')
    load_parser.add_argument('--search', nargs='+', metavar='KEYWORD', help='Search keywords to run immediately after loading')
    load_parser.add_argument('--exact', action='store_true', help='Whole-word search match')
    load_parser.add_argument('--case-sensitive', action='store_true', help='Case-sensitive search')
    load_parser.add_argument('--all', dest='match_all', action='store_true', help='All keywords must appear on the same line')
    load_parser.add_argument('--sample-size', type=int, default=80, help='Search result preview length (default: 80)')
    load_parser.add_argument('--line', type=int, nargs=2, metavar=('START', 'COUNT'), help='Slice source files: start at line START (1-based) and take COUNT lines. Creates a new manifest hash for each slice so the agent can drill into a big section recursively.')
    load_parser.add_argument('--help-examples', action='store_true', help='Print copy-paste recipes for load and exit')
    load_parser.add_argument('--help-use-cases', action='store_true', help='Print trigger -> command mapping for load and exit')

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

    get_parser = subparsers.add_parser('get', help='Retrieve content by reference')
    get_parser.add_argument('manifest', help='Manifest hash')
    get_parser.add_argument('--chapter', type=int, help='Chapter number')
    get_parser.add_argument('--section', type=int, help='Section number')
    get_parser.add_argument('--subsection', type=int, help='Subsection number')
    get_parser.add_argument('--page', type=int, help='Page number')
    get_parser.add_argument('--block', type=int, help='Block number')
    get_parser.add_argument('--help-examples', action='store_true', help='Print copy-paste recipes for get and exit')
    get_parser.add_argument('--help-use-cases', action='store_true', help='Print trigger -> command mapping for get and exit')

    search_parser = subparsers.add_parser('search', help='Search for keywords and return hits with container context')
    search_parser.add_argument('keywords', nargs='+', help='Keywords to search for')
    search_parser.add_argument('--manifests', nargs='+', required=True, help='One or more manifest hashes to search')
    search_parser.add_argument('--exact', action='store_true', help='Match whole words only')
    search_parser.add_argument('--case-sensitive', action='store_true', help='Case-sensitive matching (default: case-insensitive)')
    search_parser.add_argument('--all', dest='match_all', action='store_true', help='All keywords must appear on the same line (default: any keyword matches)')
    search_parser.add_argument('--sample-size', type=int, default=80, help='Preview length per hit (default: 80)')
    search_parser.add_argument('--help-examples', action='store_true', help='Print copy-paste recipes for search and exit')
    search_parser.add_argument('--help-use-cases', action='store_true', help='Print trigger -> command mapping for search and exit')

    cite_parser = subparsers.add_parser('cite', help='Cite a line range of a loaded item (moves it into references, keeping its id)')
    cite_parser.add_argument('item_id', help='Cache id or reference id')
    cite_parser.add_argument('start_line', type=int, help='First line (1-based, inclusive)')
    cite_parser.add_argument('end_line', type=int, help='Last line (1-based, inclusive)')
    cite_parser.add_argument('--help-examples', action='store_true', help='Print copy-paste recipes for cite and exit')
    cite_parser.add_argument('--help-use-cases', action='store_true', help='Print trigger -> command mapping for cite and exit')

    return parser


def parse_args(argv: List[str]) -> argparse.Namespace:
    """Parse command-line arguments for FastReader CLI."""
    return build_parser().parse_args(argv)


def intercept_help_content_flags_before_argparse(argv: List[str]) -> bool:
    """Handle --help-examples and --help-use-cases before argparse parses the
    rest, because those flags should not require the subcommand's positional
    arguments (e.g. `toc --help-examples` shouldn't fail for missing hash).

    Returns True if a help-content flag was handled (caller should return).
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

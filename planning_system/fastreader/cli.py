"""Local fastReader runner: argument_parsing -> commands over the local FileReaderCache -> output_formatting.

The server runs the same commands over its temp-cache adapter; the `planning` CLI reuses
argument_parsing and output_formatting and sends requests to the server instead.
"""
import os
import sys
from typing import List, Optional

from .argument_parsing import (  # noqa: F401  (re-exported)
    VALID_SUBCOMMAND_NAMES, intercept_help_content_flags_before_argparse, parse_args,
    print_help_examples_for_subcommand, print_help_use_cases_for_subcommand)
from .cache import FileReaderCache
from .commands.get import run_get
from .commands.load import run_load
from .commands.search import run_search
from .commands.toc import run_toc
from . import output_formatting
from .scanner import load_config

DEFAULT_CACHE_DIR = os.path.expanduser("~/.fastReader/cache")
DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")


def _toc_marker_types(args) -> List[str]:
    marker_types = []
    if args.chapters: marker_types.append('chapter')
    if args.sections: marker_types.append('section')
    if args.subsections: marker_types.append('subsection')
    if args.pages: marker_types.append('page_break')
    if args.blocks: marker_types.append('block')
    if args.indent_depth is not None: marker_types.append(f'indent_depth_{args.indent_depth}')
    if args.bracket_depth is not None: marker_types.append(f'bracket_depth_{args.bracket_depth}')
    if args.tag_depth is not None: marker_types.append(f'tag_depth_{args.tag_depth}')
    return marker_types or ['section']


def main(argv: Optional[List[str]] = None):
    """Main entry point for the local FastReader CLI."""
    if argv is None:
        argv = sys.argv[1:]

    if intercept_help_content_flags_before_argparse(argv):
        return

    args = parse_args(argv)
    os.makedirs(DEFAULT_CACHE_DIR, exist_ok=True)
    cache = FileReaderCache(DEFAULT_CACHE_DIR)
    config = load_config(DEFAULT_CONFIG_PATH)

    if args.command == 'load':
        loaded = []
        start = args.line[0] if args.line else None
        count = args.line[1] if args.line else None
        for file_path in args.files:
            try:
                result = run_load(file_path, cache, config,
                                  slice_starting_line=start, slice_line_count=count)
            except FileNotFoundError as e:
                print(f"Error: {e}", file=sys.stderr)
                continue
            loaded.append({"source": file_path, **result})
        if loaded:
            print(output_formatting.format_load(loaded))
        if args.search and loaded:
            try:
                search_results = run_search(
                    [item['cache_id'] for item in loaded], cache,
                    keywords=args.search, exact=args.exact,
                    case_sensitive=args.case_sensitive, match_all=args.match_all,
                    preview_length=args.sample_size,
                )
                print(output_formatting.format_inline_search(args.search, search_results))
            except FileNotFoundError as e:
                print(f"Search error: {e}", file=sys.stderr)

    elif args.command == 'toc':
        try:
            entries = run_toc(
                args.manifest, cache,
                marker_types=_toc_marker_types(args),
                preview_length=args.sample_size,
                limit=args.limit if args.limit > 0 else None,
                end_preview_length=args.end_sample_size,
            )
            print(output_formatting.format_toc(entries, args.manifest, args.sample_size,
                                               args.end_sample_size, args.show_line_range_count))
        except FileNotFoundError as e:
            print(output_formatting.format_error(str(e)), file=sys.stderr)
            sys.exit(1)

    elif args.command == 'get':
        try:
            print(output_formatting.format_get(run_get(
                args.manifest, cache, chapter=args.chapter, section=args.section,
                subsection=args.subsection, page=args.page, block=args.block)))
        except FileNotFoundError as e:
            print(output_formatting.format_error(str(e)), file=sys.stderr)
            sys.exit(1)

    elif args.command == 'search':
        try:
            results = run_search(
                args.manifests, cache, keywords=args.keywords, exact=args.exact,
                case_sensitive=args.case_sensitive, match_all=args.match_all,
                preview_length=args.sample_size,
            )
            text = output_formatting.format_search(results)
            if text:
                print(text)
        except FileNotFoundError as e:
            print(output_formatting.format_error(str(e)), file=sys.stderr)
            sys.exit(1)

    elif args.command == 'cite':
        print("cite needs the server's reference library; use `planning cite`.", file=sys.stderr)
        sys.exit(1)

    elif args.command is None:
        parse_args(['--help'])
    else:
        print(f"Command {args.command} not implemented yet.")


if __name__ == "__main__":
    main()

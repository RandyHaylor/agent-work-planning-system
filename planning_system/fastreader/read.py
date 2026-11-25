import argparse
import sys


def run_read(file_path: str, offset: int = 0, limit: int = 2000) -> str:
    """Read a file and return lines with line numbers, matching the Read tool format."""
    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
        lines = f.readlines()

    start = offset
    end = offset + limit
    selected = lines[start:end]

    return "".join(
        f"{start + i + 1}\t{line}" for i, line in enumerate(selected)
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog='fastReader.read', description='Read a file with line numbers')
    parser.add_argument('file', help='Path to file')
    parser.add_argument('--offset', type=int, default=0, help='Line to start from (0-indexed, default: 0)')
    parser.add_argument('--limit', type=int, default=2000, help='Number of lines to read (default: 2000)')
    args = parser.parse_args()

    try:
        print(run_read(args.file, offset=args.offset, limit=args.limit), end='')
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

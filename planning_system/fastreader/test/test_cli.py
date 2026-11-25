import pytest
from fastReader.cli import parse_args

def test_load_subcommand():
    """Test parsing 'load <file>' correctly (file path as positional arg)."""
    args = parse_args(['load', '/path/to/file.md'])
    assert args.command == 'load'
    assert args.files == ['/path/to/file.md']

def test_toc_chapters():
    """Test parsing 'toc --chapters <hash>' correctly (manifest as positional arg)."""
    args = parse_args(['toc', '--chapters', 'somehash'])
    assert args.command == 'toc'
    assert args.chapters is True
    assert args.manifest == 'somehash'

def test_toc_sections_with_sample_size():
    """Test parsing 'toc --sections --sample-size 60 <hash>' correctly (manifest as positional arg)."""
    args = parse_args(['toc', '--sections', '--sample-size', '60', 'hash123'])
    assert args.command == 'toc'
    assert args.sections is True
    assert args.sample_size == 60
    assert args.manifest == 'hash123'

def test_get_chapter():
    """Test parsing 'get --chapter 3 <hash>' correctly (manifest as positional arg)."""
    args = parse_args(['get', '--chapter', '3', 'hash456'])
    assert args.command == 'get'
    assert args.chapter == 3
    assert args.manifest == 'hash456'

def test_get_block():
    """Test parsing 'get --block 7 <hash>' correctly (manifest as positional arg)."""
    args = parse_args(['get', '--block', '7', 'hash789'])
    assert args.command == 'get'
    assert args.block == 7
    assert args.manifest == 'hash789'

def test_get_subsection():
    """Test parsing 'get --subsection 5 <hash>' correctly (manifest as positional arg)."""
    args = parse_args(['get', '--subsection', '5', 'hash000'])
    assert args.command == 'get'
    assert args.subsection == 5
    assert args.manifest == 'hash000'

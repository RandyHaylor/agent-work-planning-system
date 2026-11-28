"""Module boundaries: runs the import-linter contracts in pyproject.toml (same as `lint-imports`).
Each domain package is imported only through its __init__; domain does not import the layers above it."""
from pathlib import Path

from importlinter.cli import lint_imports

PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"


def test_import_contracts_are_kept():
    assert lint_imports(config_filename=str(PYPROJECT), no_cache=True, no_logo=True) == 0

import pytest
import os
from fastReader.scanner import load_config


@pytest.fixture
def config_path():
    """Fixture providing the path to the configuration file."""
    return os.path.join(os.path.dirname(__file__), '..', 'config.json')


@pytest.fixture
def config(config_path):
    """Fixture providing the loaded configuration."""
    return load_config(config_path)


@pytest.fixture
def fixture_dir():
    """Fixture providing the path to the test fixtures directory."""
    return os.path.join(os.path.dirname(__file__), 'fixtures')


@pytest.fixture
def markdown_fixture_path(fixture_dir):
    """Fixture providing the path to the markdown test document."""
    return os.path.join(fixture_dir, 'markdown_doc.md')


@pytest.fixture
def plain_text_fixture_path(fixture_dir):
    """Fixture providing the path to the plain text test document."""
    return os.path.join(fixture_dir, 'plain_text.txt')


@pytest.fixture
def minimal_fixture_path(fixture_dir):
    """Fixture providing the path to the minimal test document."""
    return os.path.join(fixture_dir, 'minimal_doc.txt')


@pytest.fixture
def dense_fixture_path(fixture_dir):
    """Fixture providing the path to the dense test document."""
    return os.path.join(fixture_dir, 'dense_doc.md')

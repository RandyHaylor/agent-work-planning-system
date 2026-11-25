# FastReader Tests

Run from the project root (`tdd-test-llm-reader/`):

```bash
# Run all tests
python3 -m pytest

# Run with verbose output
python3 -m pytest -v

# Stop on first failure
python3 -m pytest -x

# Run a specific test file
python3 -m pytest fastReader/test/test_scanner.py

# Run a specific test by name
python3 -m pytest -k "test_load_command"
```

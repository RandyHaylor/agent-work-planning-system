"""Smoke tests for the fastReader.sh wrapper (Linux/macOS).

The wrapper's job is to:
  1. Compute PYTHONPATH as the PARENT of its own directory.
  2. Dispatch argv[1] as the subcommand (`load|toc|get|search`).
  3. Forward the rest of argv verbatim to `python -m fastReader.<subcmd>`.

On Windows the parallel `fastReader.bat` is tested manually; skipped here.
"""
import os
import platform
import subprocess
import tempfile

import pytest

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WRAPPER_SH_PATH = os.path.join(SKILL_DIR, "fastReader.sh")

pytestmark = pytest.mark.skipif(
    platform.system() == "Windows" or not os.path.exists(WRAPPER_SH_PATH),
    reason="fastReader.sh wrapper is POSIX-only; .bat is tested on Windows.",
)


def run_wrapper_with_args_and_capture_output(*args_to_forward):
    """Run fastReader.sh with the given argv tail and return (stdout, stderr, returncode)."""
    completed_process = subprocess.run(
        [WRAPPER_SH_PATH, *args_to_forward],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return completed_process.stdout, completed_process.stderr, completed_process.returncode


def test_wrapper_prints_help_when_no_args_given_and_exits_zero():
    # No args is treated as "show help", not an error.
    stdout, _stderr, returncode = run_wrapper_with_args_and_capture_output()
    assert returncode == 0
    assert "usage: fastReader" in stdout
    assert "load" in stdout and "toc" in stdout and "get" in stdout and "search" in stdout


def test_wrapper_rejects_unknown_subcommand_with_exit_code_2():
    _stdout, stderr, returncode = run_wrapper_with_args_and_capture_output("frobnicate", "whatever")
    assert returncode == 2
    assert "unknown subcommand" in stderr


def test_wrapper_forwards_toc_help_examples_without_requiring_manifest_arg():
    stdout, _stderr, returncode = run_wrapper_with_args_and_capture_output("toc", "--help-examples")
    assert returncode == 0
    assert "Copy-paste examples for: fastReader.toc" in stdout


def test_wrapper_forwards_search_help_use_cases():
    stdout, _stderr, returncode = run_wrapper_with_args_and_capture_output("search", "--help-use-cases")
    assert returncode == 0
    assert "Trigger -> command mapping for: fastReader.search" in stdout


def test_wrapper_load_on_tiny_tempfile_returns_count_summary_and_hash():
    """End-to-end: the wrapper must compute PYTHONPATH correctly so python can
    import the fastReader package; a tiny markdown file should produce a count
    summary with a manifest hash suffix on the Browse hint."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        test_markdown_file_path = os.path.join(tmp_dir, "wrapper_smoketest_doc.md")
        with open(test_markdown_file_path, "w") as fh:
            fh.write("# Chapter 1\nline a\n## Section A\nline b\n## Section B\nline c\n")
        stdout, stderr, returncode = run_wrapper_with_args_and_capture_output(
            "load", test_markdown_file_path
        )
    assert returncode == 0, f"wrapper load failed: stderr={stderr!r}"
    assert "Chapters:" in stdout
    assert "Sections:" in stdout
    # agent_instructions.json now emits wrapper-form Browse hints, not raw python.
    assert "Browse: fastReader.sh toc" in stdout


def test_wrapper_help_flag_alone_prints_usage_and_exits_zero():
    stdout, _stderr, returncode = run_wrapper_with_args_and_capture_output("--help")
    assert returncode == 0
    assert "fastReader" in stdout


def run_wrapper_with_custom_json_bin_env_var(json_bin_path_override, *args_to_forward):
    """Same as run_wrapper_... but sets FAST_READER_JSON_BIN in the child env
    so we can simulate 'quick-json-reader installed' and 'not installed'
    without touching the real ~/.claude/skills/quick-json-reader folder."""
    child_env = dict(os.environ)
    child_env["FAST_READER_JSON_BIN"] = json_bin_path_override
    completed_process = subprocess.run(
        [WRAPPER_SH_PATH, *args_to_forward],
        capture_output=True,
        text=True,
        timeout=30,
        env=child_env,
    )
    return completed_process.stdout, completed_process.stderr, completed_process.returncode


def test_wrapper_help_lists_json_as_not_installed_when_binary_absent(tmp_path):
    missing_bin_path = str(tmp_path / "does_not_exist_quick_json_reader")
    stdout, _stderr, returncode = run_wrapper_with_custom_json_bin_env_var(missing_bin_path)
    assert returncode == 0
    assert "json" in stdout
    assert "NOT INSTALLED" in stdout
    assert "quick-json-reader" in stdout


def test_wrapper_json_subcommand_errors_with_install_hint_when_binary_absent(tmp_path):
    missing_bin_path = str(tmp_path / "does_not_exist_quick_json_reader")
    _stdout, stderr, returncode = run_wrapper_with_custom_json_bin_env_var(
        missing_bin_path, "json", "some_file.json"
    )
    assert returncode == 3
    assert "requires the quick-json-reader skill" in stderr
    assert missing_bin_path in stderr


def test_wrapper_detects_json_binary_and_passes_through_when_present(tmp_path):
    """Simulate a present quick-json-reader by pointing FAST_READER_JSON_BIN
    at a tiny fake-binary script that prints a sentinel and exits 0."""
    fake_json_binary_path = tmp_path / "fake_quick_json_reader_binary"
    fake_json_binary_path.write_text(
        "#!/bin/bash\necho FAKE_QUICK_JSON_READER_SAW:\"$@\"\nexit 0\n"
    )
    fake_json_binary_path.chmod(0o755)

    stdout, _stderr, help_returncode = run_wrapper_with_custom_json_bin_env_var(
        str(fake_json_binary_path)
    )
    assert help_returncode == 0
    # When json is available the wrapper prints wrapper_help_json_on.txt,
    # which integrates `json` into the subcommand list as a first-class option.
    assert "load | toc | get | search | json" in stdout

    stdout, _stderr, pass_returncode = run_wrapper_with_custom_json_bin_env_var(
        str(fake_json_binary_path), "json", "some_file.json", "--search-vals", "error"
    )
    assert pass_returncode == 0
    assert "FAKE_QUICK_JSON_READER_SAW:some_file.json --search-vals error" in stdout


def test_wrapper_unknown_subcommand_message_adjusts_to_json_availability(tmp_path):
    # On unknown subcommand, stderr begins with the error line and then prints
    # the full help text (wrapper_help_json_{on,off}.txt). The help body
    # reveals whether the `json` subcommand is available.
    missing_bin_path = str(tmp_path / "does_not_exist_quick_json_reader")
    _stdout, stderr_absent, returncode_absent = run_wrapper_with_custom_json_bin_env_var(
        missing_bin_path, "frobnicate"
    )
    assert returncode_absent == 2
    assert "unknown subcommand 'frobnicate'" in stderr_absent
    assert "NOT INSTALLED" in stderr_absent            # from wrapper_help_json_off.txt
    assert "load | toc | get | search" in stderr_absent
    assert "| json" not in stderr_absent               # json not advertised when absent

    fake_json_binary_path = tmp_path / "fake_quick_json_reader_binary_for_unknown_subcmd"
    fake_json_binary_path.write_text("#!/bin/bash\nexit 0\n")
    fake_json_binary_path.chmod(0o755)
    _stdout, stderr_present, returncode_present = run_wrapper_with_custom_json_bin_env_var(
        str(fake_json_binary_path), "frobnicate"
    )
    assert returncode_present == 2
    assert "unknown subcommand 'frobnicate'" in stderr_present
    assert "load | toc | get | search | json" in stderr_present   # from wrapper_help_json_on.txt

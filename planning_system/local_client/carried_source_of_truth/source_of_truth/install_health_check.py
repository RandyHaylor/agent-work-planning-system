"""Non-destructive install health check, run automatically at register time.

Re-asserts the deployed install WITHOUT the one-time bootstrap's destructive
copy/backup: ensures the hook wrapper scripts, the settings.json hook entries,
the on-PATH wrapper, and the global settings file are present and current.
Idempotent — a healthy install is left effectively unchanged.

The actual install logic lives in the top-level `install.py` (which is deployed
into the skill folder alongside this package, so it is importable at runtime).
We reuse it here so there is exactly one definition of "what a healthy install
looks like." All sub-step output is suppressed; the caller prints one summary
line. Best-effort: this never raises, so it can never block the caller's
primary action (registration)."""
from __future__ import annotations

import contextlib
import io


def run_install_health_check_quietly() -> bool:
    """Verify/repair the deployed install, suppressing all sub-step output.

    Returns True if the health check ran to completion, False if it could not
    run (e.g. the installer module wasn't importable in this context)."""
    try:
        import install as installer_module  # deployed next to this package
    except Exception:
        return False
    try:
        install_dir = installer_module.install_dir_path()
        settings_path = installer_module.settings_json_path()
        python_launcher = installer_module.python_launcher_for_current_platform()
        with contextlib.redirect_stdout(io.StringIO()):
            installer_module.write_wrapper_scripts(install_dir)
            installer_module.ensure_settings_json_hook_entries(
                install_dir, settings_path, python_launcher
            )
            skill_folder_wrapper_path = (
                installer_module.write_skill_folder_source_of_truth_wrapper(install_dir)
            )
            installer_module.write_path_stub_forwarding_to_skill_folder_wrapper(
                skill_folder_wrapper_path
            )
            installer_module.initialize_global_settings_file()
    except Exception:
        return False
    return True

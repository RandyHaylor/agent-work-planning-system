"""Backgrounded, title-only review for the non-blocking reviewer default.

When REVIEWER_TITLE_ONLY_NONBLOCKING is ON, submit_requirements_tree_change_set
applies every op immediately and then DETACHES this work: a separate process
(spawned via spawn_background_title_review) generalizes only the node TITLES,
applies any amendments under the existing file lock, and enqueues one
pending-message note per CHANGED title (surfaced by the existing PostToolUse
drainer on the agent's next turn).

The model call is injected so tests never fork a process or call a model:
  * run_title_review_and_enqueue_notes(project_id, node_ids, model_caller)
    is the PURE, directly-testable core; model_caller(prompt_text) -> reply_text.
  * spawn_background_title_review(project_id, node_ids) is the default detached
    spawn (subprocess.Popen, start_new_session=True, output discarded). It is
    monkeypatched out in tests.
  * `python3 -m source_of_truth.background_title_reviewer <project_id> <nd-ids...>`
    is the detached entry point; it wires the REAL model_caller to the core.
"""
from __future__ import annotations

import subprocess
import sys
from typing import Callable

from .id_display import strip_node_id_input_prefix
from .pending_messages_for_raw_input_sender import add_pending_message_for_raw_input_sender
from .requirements_modification_reviewer import (
    build_title_generalization_prompt,
    parse_generalized_titles_from_response,
)
from .requirements_tree_store import (
    load_requirements_tree,
    save_requirements_tree_atomically,
)

ModelCaller = Callable[[str], str]


def run_title_review_and_enqueue_notes(
    project_id: str,
    node_ids: list[str],
    model_caller: ModelCaller,
) -> list[str]:
    """Generalize the titles of the given nodes; persist changes; enqueue notes.

    Pure except for the (injected) model_caller and the existing tree/queue I/O.
    Returns the list of note strings enqueued (one per CHANGED title); unchanged
    or missing titles enqueue nothing. Applies amendments under the tree file
    lock so a concurrent writer never interleaves with the read-modify-write.
    """
    normalized_node_ids = [strip_node_id_input_prefix(nid) for nid in node_ids]

    # No outer file lock here: save_requirements_tree_atomically takes the
    # (non-reentrant) tree lock itself, so wrapping it would self-deadlock. This
    # matches how the rest of the codebase mutates the tree (load -> modify ->
    # atomic save); the brief read-modify-write window is acceptable for this
    # best-effort, non-blocking title amendment.
    tree = load_requirements_tree(project_id)
    titles_by_node_id: dict[str, str] = {}
    for node_id in normalized_node_ids:
        node = tree.nodes_by_id.get(node_id)
        if node is not None and node.short_neutral_title:
            titles_by_node_id[node_id] = node.short_neutral_title
    if not titles_by_node_id:
        return []

    prompt_text = build_title_generalization_prompt(titles_by_node_id)
    response_text = model_caller(prompt_text)
    generalized_by_node_id = parse_generalized_titles_from_response(
        response_text, valid_node_ids=set(titles_by_node_id.keys())
    )

    enqueued_notes: list[str] = []
    changed = False
    for node_id, old_title in titles_by_node_id.items():
        new_title = generalized_by_node_id.get(node_id)
        if not new_title or new_title == old_title:
            continue
        tree.nodes_by_id[node_id].short_neutral_title = new_title
        changed = True
        enqueued_notes.append(
            f"node title {old_title!r} generalized to {new_title!r} — "
            f"titles cannot include specific requirement details"
        )
    if changed:
        save_requirements_tree_atomically(tree)

    for note in enqueued_notes:
        add_pending_message_for_raw_input_sender(note, target_project_id=project_id)
    return enqueued_notes


def _real_model_caller_for_project(project_id: str) -> ModelCaller:
    """A one-shot model caller using the project's resolved reviewer command/model.

    Runs `<reviewer_command...> --model <model>` with the prompt on stdin and
    returns stdout. Intentionally NOT used in tests (they inject a stub).
    """
    from .load_config import resolve_effective_global_settings

    settings = resolve_effective_global_settings(project_id)

    def model_caller(prompt_text: str) -> str:
        command = list(settings.reviewer_command) + ["--model", settings.reviewer_model_name]
        completed = subprocess.run(
            command,
            input=prompt_text,
            capture_output=True,
            text=True,
            timeout=120,
        )
        return completed.stdout or ""

    return model_caller


def spawn_background_title_review(project_id: str, node_ids: list[str]) -> None:
    """Detach a background process to run the title review; do NOT await it.

    Default production behavior; monkeypatched out in tests so nothing forks.
    """
    if not node_ids:
        return
    command = [
        sys.executable, "-m", "source_of_truth.background_title_reviewer",
        project_id, *[str(nid) for nid in node_ids],
    ]
    subprocess.Popen(
        command,
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
    )


def _main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(
            "Usage: python3 -m source_of_truth.background_title_reviewer "
            "<project_id> <nd-id> [<nd-id> ...]",
            file=sys.stderr,
        )
        return 2
    project_id = argv[0]
    node_ids = argv[1:]
    run_title_review_and_enqueue_notes(
        project_id, node_ids, _real_model_caller_for_project(project_id)
    )
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))

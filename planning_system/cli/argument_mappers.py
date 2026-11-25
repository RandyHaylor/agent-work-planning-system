"""argument_mappers: the few commands whose parsed arguments are reshaped before their one call.
Named in command_table by CommandSpec.mapper. Pure reshaping; no business logic."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from planning_system.api_client import PlanningApiClientInterface
from planning_system.local_client.task_runner import TASK_ROLES, TaskStartRequest

DEFAULT_ROLE = TASK_ROLES[0]

Mapper = Callable[[dict, PlanningApiClientInterface], dict]


def drop_unset(arguments: dict, api) -> dict:
    return {key: value for key, value in arguments.items() if value is not None}


def text_or_file(arguments: dict, api) -> dict:
    file_name = arguments.pop("file")
    text = arguments.pop("text")
    return {**drop_unset(arguments, api), "text": text if text is not None else Path(file_name).read_text()}


def own_task(arguments: dict, api) -> dict:
    """supplementary create targets the caller's own task: its credential's scope node (GET /me)."""
    return {"node_id": api.me()["scope_node_id"], **arguments}


def task_start_request(arguments: dict, api) -> dict:
    return {"request": TaskStartRequest(arguments["node_id"], arguments["agent_id"],
                                        arguments["role"] or DEFAULT_ROLE, arguments["token"],
                                        Path(arguments["working_directory"]),
                                        allowed_tools=tuple(arguments.get("allowed_tools") or ()),
                                        model=arguments.get("model"))}


def load_source(arguments: dict, api) -> dict:
    """load URL|FILE: a http(s) source is a URL, anything else a local file path."""
    source = (arguments.pop("source") or [None])[0]
    location = {} if source is None else (
        {"url": source} if source.startswith(("http://", "https://")) else {"file_path": Path(source)})
    return {**drop_unset(arguments, api), **location}


MAPPERS: dict[str, Mapper] = {
    "drop_unset": drop_unset, "text_or_file": text_or_file, "own_task": own_task,
    "task_start_request": task_start_request, "load_source": load_source,
}

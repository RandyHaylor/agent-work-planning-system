"""The command-line version of the prompt-builder page. Everything the page does — pick a
preset, switch rules on and off, choose options, edit text, reorder, add custom text,
add your own options, categories and presets, and produce the text to paste — is a
command here, working on a ruleset JSON file. `serve` opens the page itself.

Run `python -m ai_prompt_builder --help` from the repository folder for the command list.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from .rule_catalog import RuleCatalog, read_json, write_json
from .ruleset import (
    compose_prompt_text,
    find_entry,
    find_or_add_entry,
    list_rules_not_added_yet,
    new_ruleset,
    text_of_entry,
)


def print_json(content) -> None:
    print(json.dumps(content, indent=2, ensure_ascii=False))


def read_text_argument(arguments, text_name="text", file_name="text_file") -> "str | None":
    if getattr(arguments, file_name, None):
        return Path(getattr(arguments, file_name)).read_text(encoding="utf-8")
    return getattr(arguments, text_name, None)


def load_ruleset(path: str) -> dict:
    return read_json(Path(path))


# --- browsing the catalog ----------------------------------------------------------------

def command_categories(catalog: RuleCatalog, arguments) -> None:
    categories = catalog.list_categories()
    if arguments.json:
        return print_json(categories)
    for category in categories:
        print(f"{category['categoryId']}  —  {category['categoryName']}")
        for option in category["options"]:
            mark = " (yours)" if option.get("isCustom") else ""
            print(f"    {option['optionId']}: {option['shortName']}{mark}")


def command_category(catalog: RuleCatalog, arguments) -> None:
    category = catalog.find_category(arguments.category_id)
    if category is None:
        sys.exit(f"no category '{arguments.category_id}' (see: categories)")
    if arguments.json:
        return print_json(category)
    print(f"# {category['categoryName']}  ({category['categoryId']})\n")
    for option in category["options"]:
        print(f"## {option['shortName']}  ({option['optionId']})\n\n{option['fullText']}\n")


def command_presets(catalog: RuleCatalog, arguments) -> None:
    presets = catalog.list_presets()
    if arguments.json:
        return print_json(presets)
    for preset in presets:
        mark = " (yours)" if preset.get("isCustom") else ""
        default = " (default)" if preset["name"] == catalog.preset_selected_by_default else ""
        rules_on = sum(1 for entry in preset["entries"] if entry.get("enabled", True))
        print(f"{preset['name']}{mark}{default} — {rules_on} rules on")


# --- making and changing a ruleset -------------------------------------------------------

def command_new(catalog: RuleCatalog, arguments) -> None:
    preset = None
    if arguments.preset:
        preset = catalog.find_preset(arguments.preset)
        if preset is None:
            sys.exit(f"no preset '{arguments.preset}' (see: presets)")
    elif not arguments.blank:
        preset = catalog.find_preset(catalog.preset_selected_by_default)
    ruleset = new_ruleset(catalog, preset, name=arguments.name)
    rules_not_found = ruleset.pop("rulesNotFound", [])
    write_json(Path(arguments.ruleset_file), ruleset)
    print(f"wrote {arguments.ruleset_file}")
    if rules_not_found:
        print("warning, these rules were not found: " + ", ".join(rules_not_found)
              + ". They were left out. To update the preset, save it again: save-preset "
              + f"{arguments.ruleset_file} \"{preset['name']}\" (your own presets only).",
              file=sys.stderr)


def command_show(catalog: RuleCatalog, arguments) -> None:
    ruleset = load_ruleset(arguments.ruleset_file)
    if arguments.json:
        return print_json(ruleset)
    print(f"Ruleset: {ruleset.get('name', 'Untitled')}")
    custom = ruleset.get("customText") or {}
    state = "on" if custom.get("enabled", True) else "off"
    print(f"Custom text ({state}, at {custom.get('placement', 'end')}): {custom.get('text') or '(empty)'}\n")
    for number, entry in enumerate(ruleset["entries"], start=1):
        category = catalog.find_category(entry["categoryId"]) or {"categoryName": entry["categoryId"]}
        option = catalog.find_option(entry["categoryId"], entry["optionId"]) or {"shortName": entry["optionId"]}
        switch = "ON " if entry.get("enabled", True) else "off"
        edited = "  [text edited]" if entry.get("editedText") is not None else ""
        print(f"{number:>2}. [{switch}] {category['categoryName']}: {option['shortName']}"
              f"  ({entry['categoryId']} / {entry['optionId']}){edited}")
        if arguments.full and entry.get("enabled", True):
            for line in (text_of_entry(catalog, entry) or "").splitlines():
                print(f"       {line}")
    not_added = list_rules_not_added_yet(catalog, ruleset)
    if not_added:
        print("\nNot added yet: " + ", ".join(
            f"{c['categoryName']} ({c['categoryId']})" for c in not_added))


def command_set(catalog: RuleCatalog, arguments) -> None:
    ruleset = load_ruleset(arguments.ruleset_file)
    entry = find_or_add_entry(catalog, ruleset, arguments.category_id)
    if arguments.option:
        if catalog.find_option(arguments.category_id, arguments.option) is None:
            sys.exit(f"no option '{arguments.option}' in '{arguments.category_id}' "
                     f"(see: category {arguments.category_id})")
        entry["optionId"] = arguments.option
        entry["editedText"] = None
    if arguments.on:
        entry["enabled"] = True
    if arguments.off:
        entry["enabled"] = False
    text = read_text_argument(arguments)
    if text is not None:
        entry["editedText"] = text
    if arguments.reset_text:
        entry["editedText"] = None
    write_json(Path(arguments.ruleset_file), ruleset)
    print(f"updated {arguments.category_id}")


def command_all(catalog: RuleCatalog, arguments) -> None:
    ruleset = load_ruleset(arguments.ruleset_file)
    for entry in ruleset["entries"]:
        if arguments.action == "on":
            entry["enabled"] = True
        elif arguments.action == "off":
            entry["enabled"] = False
        else:
            entry["editedText"] = None
    write_json(Path(arguments.ruleset_file), ruleset)
    print(f"all rules: {arguments.action}")


def command_move(catalog: RuleCatalog, arguments) -> None:
    ruleset = load_ruleset(arguments.ruleset_file)
    entry = find_entry(ruleset, arguments.category_id)
    ruleset["entries"].remove(entry)
    position = max(1, min(arguments.position, len(ruleset["entries"]) + 1))
    ruleset["entries"].insert(position - 1, entry)
    write_json(Path(arguments.ruleset_file), ruleset)
    print(f"moved {arguments.category_id} to position {position}")


def command_remove(catalog: RuleCatalog, arguments) -> None:
    ruleset = load_ruleset(arguments.ruleset_file)
    ruleset["entries"].remove(find_entry(ruleset, arguments.category_id))
    write_json(Path(arguments.ruleset_file), ruleset)
    print(f"removed {arguments.category_id} from this ruleset (it is 'not added yet' now; "
          f"switching it off keeps it in the list instead)")


def command_delete_rule(catalog: RuleCatalog, arguments) -> None:
    catalog.delete_rule(arguments.category_id)
    print(f"deleted rule {arguments.category_id} for good (saved in {catalog.user_folder})")


def command_custom_text(catalog: RuleCatalog, arguments) -> None:
    ruleset = load_ruleset(arguments.ruleset_file)
    custom = ruleset.setdefault("customText", {"text": "", "placement": "end", "enabled": True})
    text = read_text_argument(arguments)
    if text is not None:
        custom["text"] = text
    if arguments.at:
        custom["placement"] = arguments.at
    if arguments.on:
        custom["enabled"] = True
    if arguments.off:
        custom["enabled"] = False
    write_json(Path(arguments.ruleset_file), ruleset)
    print("updated custom text")


def command_compose(catalog: RuleCatalog, arguments) -> None:
    text = compose_prompt_text(catalog, load_ruleset(arguments.ruleset_file))
    if arguments.out:
        Path(arguments.out).write_text(text + "\n", encoding="utf-8")
        print(f"wrote {arguments.out}")
    else:
        print(text)


# --- the user's own additions ------------------------------------------------------------

def command_add_option(catalog: RuleCatalog, arguments) -> None:
    option_id = catalog.add_custom_option(arguments.category_id, arguments.name, read_text_argument(arguments))
    print(f"added option {option_id} to {arguments.category_id} (saved in {catalog.user_folder})")


def command_add_category(catalog: RuleCatalog, arguments) -> None:
    category_id = catalog.add_custom_category(arguments.name)
    print(f"added category {category_id}; add its options with: add-option {category_id} ...")


def command_save_preset(catalog: RuleCatalog, arguments) -> None:
    path = catalog.save_user_preset(load_ruleset(arguments.ruleset_file), arguments.name)
    print(f"saved preset '{arguments.name}' to {path}")


def command_where(catalog: RuleCatalog, arguments) -> None:
    print(catalog.user_folder)


# --- the web page ------------------------------------------------------------------------

def command_serve(catalog: RuleCatalog, arguments) -> None:
    from .local_web_server import RuleBuilderSession, start_server

    opened = Path(arguments.ruleset_file).resolve() if arguments.ruleset_file else None
    send_file = Path(arguments.send_to_agent_file).resolve() if arguments.send_to_agent_file else None
    server = start_server(RuleBuilderSession(catalog, opened, send_file), port=arguments.port)
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    # One line of JSON first, so an agent can read the address without parsing prose.
    print(json.dumps({"url": url, "sendToAgentFile": str(send_file) if send_file else None,
                      "rulesetFile": str(opened) if opened else None}), flush=True)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        server.shutdown()


def command_wait_for_send(catalog: RuleCatalog, arguments) -> None:
    """Block until the Send to local AI agent button writes the send file (newer than when this
    command started), then print what was sent and exit."""
    send_file = Path(arguments.send_to_agent_file)
    started = time.time()
    previous = send_file.stat().st_mtime if send_file.exists() else None
    while True:
        if send_file.exists():
            modified = send_file.stat().st_mtime
            if (previous is None and modified >= started - 1) or (previous is not None and modified > previous):
                break
        if arguments.timeout and time.time() - started > arguments.timeout:
            sys.exit("timed out waiting for Send to local AI agent")
        time.sleep(0.5)
    time.sleep(0.2)  # let the write finish
    sent = read_json(send_file)
    print_json({"sendToAgentFile": str(send_file), "rulesetName": (sent.get("ruleset") or {}).get("name"),
                "composedText": sent.get("composedText")})


# --- argument parsing --------------------------------------------------------------------

def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ai_prompt_builder",
        description="Build the rules you give an AI agent: the command-line version of the prompt-builder page.")
    parser.add_argument("--user-folder", help="the folder for your own options, categories and presets")
    commands = parser.add_subparsers(dest="command", required=True)

    def add(name, function, help_text):
        command = commands.add_parser(name, help=help_text, description=help_text)
        command.set_defaults(run=function)
        return command

    def text_inputs(command):
        command.add_argument("--text", help="the text")
        command.add_argument("--text-file", help="read the text from this file (best for long or multi-line text)")

    for name, function, help_text in (
        ("categories", command_categories, "list every category and its options"),
        ("presets", command_presets, "list every preset"),
    ):
        add(name, function, help_text).add_argument("--json", action="store_true")
    command = add("category", command_category, "show one category's options in full")
    command.add_argument("category_id")
    command.add_argument("--json", action="store_true")

    command = add("new", command_new, "start a ruleset file, from a preset (the default one if none is named)")
    command.add_argument("ruleset_file")
    command.add_argument("--preset", help="the preset to start from")
    command.add_argument("--blank", action="store_true", help="start with every rule off")
    command.add_argument("--name", help="a name for this ruleset")

    command = add("show", command_show, "show a ruleset's rules: on/off, option, order")
    command.add_argument("ruleset_file")
    command.add_argument("--full", action="store_true", help="also print the text of each rule that is on")
    command.add_argument("--json", action="store_true")

    command = add("set", command_set,
                  "change one rule: its option, on/off, or its text (adds it if not added yet)")
    command.add_argument("ruleset_file")
    command.add_argument("category_id")
    command.add_argument("--option", help="choose this option")
    switch = command.add_mutually_exclusive_group()
    switch.add_argument("--on", action="store_true")
    switch.add_argument("--off", action="store_true")
    text_inputs(command)
    command.add_argument("--reset-text", action="store_true", help="put the option's own text back")

    command = add("all", command_all, "switch every rule on or off, or reset every rule's text")
    command.add_argument("ruleset_file")
    command.add_argument("action", choices=("on", "off", "reset-text"))

    command = add("move", command_move, "move a rule to a position (1 = first)")
    command.add_argument("ruleset_file")
    command.add_argument("category_id")
    command.add_argument("position", type=int)

    command = add("delete-rule", command_delete_rule,
                  "delete a rule from the catalog for good (your own: removed; built-in: hidden)")
    command.add_argument("category_id")

    command = add("remove", command_remove, "take a rule out of this ruleset (back to 'not added yet')")
    command.add_argument("ruleset_file")
    command.add_argument("category_id")

    command = add("custom-text", command_custom_text,
                  "set the optional custom text that makes the ruleset a specific prompt")
    command.add_argument("ruleset_file")
    text_inputs(command)
    command.add_argument("--at", choices=("end", "start"))
    switch = command.add_mutually_exclusive_group()
    switch.add_argument("--on", action="store_true")
    switch.add_argument("--off", action="store_true")

    command = add("compose", command_compose, "print the text to paste")
    command.add_argument("ruleset_file")
    command.add_argument("--out", help="write it to this file instead")

    command = add("add-option", command_add_option, "add your own option to a category")
    command.add_argument("category_id")
    command.add_argument("--name", required=True, help="short name shown in the menu")
    text_inputs(command)

    command = add("add-category", command_add_category, "add your own category")
    command.add_argument("name")

    command = add("save-preset", command_save_preset, "save a ruleset as one of your presets")
    command.add_argument("ruleset_file")
    command.add_argument("name")

    add("where", command_where, "print the folder your own options and presets are saved in")

    command = add("serve", command_serve,
                  "open the web page on a free local port; prints one JSON line with the URL first")
    command.add_argument("--ruleset-file", help="open this ruleset in the page")
    command.add_argument("--send-to-agent-file",
                         help="enable the Send to local AI agent button; clicking it writes here")
    command.add_argument("--port", type=int, default=0, help="0 (default) = any free port")

    command = add("wait-for-send", command_wait_for_send,
                  "wait until the person clicks Send to local AI agent, then print what was sent")
    command.add_argument("send_to_agent_file")
    command.add_argument("--timeout", type=float, default=0, help="seconds; 0 = wait forever")
    return parser


def main(argv=None) -> None:
    arguments = build_argument_parser().parse_args(argv)
    catalog = RuleCatalog(arguments.user_folder)
    try:
        arguments.run(catalog, arguments)
    except (KeyError, ValueError) as problem:
        sys.exit(str(problem).strip("'\""))

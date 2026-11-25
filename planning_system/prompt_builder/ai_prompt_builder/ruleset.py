"""A ruleset: one filled-in selection of rules. Presets and working instances are both
rulesets and share one file shape:

{
  "format": "ai-prompt-builder/ruleset@1",
  "name": "...",
  "entries": [                                    # in order
    {"categoryId": "...", "optionId": "...", "enabled": true, "editedText": null}
  ],
  "customText": {"text": "...", "placement": "end" | "start", "enabled": true}
}

A ruleset holds only the rules it lists (switched on or off); every other rule in the
catalog is "not added yet" and can be added. editedText, when not null, replaces the
option's text. The composed text is identical to what the web page produces.
"""

from __future__ import annotations

from .rule_catalog import RULESET_FORMAT, RuleCatalog


def new_ruleset(catalog: RuleCatalog, preset: "dict | None" = None, name: "str | None" = None) -> dict:
    source = preset or {"entries": [], "customText": {"text": "", "placement": "end", "enabled": True}}
    ruleset = {
        "format": RULESET_FORMAT,
        "name": name or (preset["name"] if preset else "Untitled"),
        "entries": [],
        "customText": dict({"text": "", "placement": "end", "enabled": True}, **(source.get("customText") or {})),
    }
    # A preset stores settings pointing at rules and options in the catalog; any that are
    # gone are left out and listed under "rulesNotFound" for the caller to report.
    ruleset["rulesNotFound"] = []
    for entry in source.get("entries", []):
        if not catalog.find_option(entry["categoryId"], entry["optionId"]):
            category = catalog.find_category(entry["categoryId"])
            deleted_built_in = next((c for c in catalog.shipped_categories
                                     if c["categoryId"] == entry["categoryId"]), None)
            ruleset["rulesNotFound"].append(
                f"{category['categoryName']} (option \"{entry['optionId']}\")" if category
                else deleted_built_in["categoryName"] if deleted_built_in
                else entry["categoryId"])
            continue
        ruleset["entries"].append({
            "categoryId": entry["categoryId"], "optionId": entry["optionId"],
            "enabled": entry.get("enabled", True) is not False,
            "editedText": entry.get("editedText"),
        })
    return ruleset


def list_rules_not_added_yet(catalog: RuleCatalog, ruleset: dict) -> list:
    present = {entry["categoryId"] for entry in ruleset["entries"]}
    return [category for category in catalog.list_categories()
            if category["categoryId"] not in present and category["options"]]


def find_or_add_entry(catalog: RuleCatalog, ruleset: dict, category_id: str) -> dict:
    """The ruleset's entry for this rule, added at the end (switched on, first option) when
    the rule is not in the ruleset yet."""
    for entry in ruleset["entries"]:
        if entry["categoryId"] == category_id:
            return entry
    category = catalog.find_category(category_id)
    if category is None or not category["options"]:
        raise KeyError(f"no rule '{category_id}' (see: categories)")
    entry = {"categoryId": category_id, "optionId": category["options"][0]["optionId"],
             "enabled": True, "editedText": None}
    ruleset["entries"].append(entry)
    return entry


def find_entry(ruleset: dict, category_id: str) -> dict:
    for entry in ruleset["entries"]:
        if entry["categoryId"] == category_id:
            return entry
    raise KeyError(f"the ruleset has no '{category_id}' rule")


def text_of_entry(catalog: RuleCatalog, entry: dict) -> "str | None":
    if entry.get("editedText") is not None:
        return entry["editedText"]
    option = catalog.find_option(entry["categoryId"], entry["optionId"])
    return option["fullText"] if option else None


def compose_rules_text(catalog: RuleCatalog, ruleset: dict) -> str:
    blocks = []
    for entry in ruleset["entries"]:
        if entry.get("enabled") is False:
            continue
        category = catalog.find_category(entry["categoryId"])
        text = text_of_entry(catalog, entry)
        if category is None or text is None:
            continue
        blocks.append(f"## {category['categoryName']}\n\n{text}")
    return "\n\n".join(blocks)


def compose_prompt_text(catalog: RuleCatalog, ruleset: dict) -> str:
    """The text to paste: each rule that is on, under its category heading, with the
    custom text (when on and not empty) at the beginning or the end."""
    rules_text = compose_rules_text(catalog, ruleset)
    custom = ruleset.get("customText") or {}
    custom_text = (custom.get("text") or "").strip() if custom.get("enabled", True) else ""
    if not custom_text:
        return rules_text
    if not rules_text:
        return custom_text
    if custom.get("placement") == "start":
        return f"{custom_text}\n\n{rules_text}"
    return f"{rules_text}\n\n{custom_text}"

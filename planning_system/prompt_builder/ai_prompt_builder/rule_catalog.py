"""The rule catalog: the shipped categories and presets (the shared JSON files in data/,
also read by the web page) plus the user's own categories, options and presets, kept as
JSON files in the user's prompt-builder folder.

The user's folder is, in order of preference:
  1. the folder named by the AI_PROMPT_BUILDER_HOME environment variable;
  2. a `.ai-prompt-builder` folder in the current working directory, if it exists
     (a team can keep its presets in its project this way);
  3. `~/.ai-prompt-builder`.

Inside it:
  customizations.json   {"customCategories": [...], "customOptions": [...]}
  presets/<name>.json   the user's presets, each a ruleset file
  instances/            a suggested place for working rulesets
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

REPOSITORY_FOLDER = Path(__file__).resolve().parent.parent
SHIPPED_DATA_FOLDER = REPOSITORY_FOLDER / "data"
RULESET_FORMAT = "ai-prompt-builder/ruleset@1"


def resolve_user_rule_builder_folder() -> Path:
    from_environment = os.environ.get("AI_PROMPT_BUILDER_HOME")
    if from_environment:
        return Path(from_environment).expanduser()
    in_current_project = Path.cwd() / ".ai-prompt-builder"
    if in_current_project.is_dir():
        return in_current_project
    return Path.home() / ".ai-prompt-builder"


def file_name_for(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "untitled"
    return slug + ".json"


def read_json(path: Path):
    with open(path, encoding="utf-8") as stream:
        return json.load(stream)


def write_json(path: Path, content) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    with open(temporary_path, "w", encoding="utf-8") as stream:
        json.dump(content, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
    os.replace(temporary_path, path)


class RuleCatalog:
    """Every category (with every option) and every preset, shipped and the user's own."""

    def __init__(self, user_folder: "Path | None" = None):
        self.user_folder = Path(user_folder) if user_folder else resolve_user_rule_builder_folder()
        self.shipped_categories = read_json(SHIPPED_DATA_FOLDER / "rule-categories.json")["categories"]
        preset_index = read_json(SHIPPED_DATA_FOLDER / "presets" / "index.json")
        self.preset_selected_by_default = preset_index["presetSelectedWhenThePageOpens"]
        self.shipped_presets = [
            read_json(SHIPPED_DATA_FOLDER / "presets" / file_name)
            for file_name in preset_index["presetFiles"]
        ]

    # --- the user's own additions ------------------------------------------------------

    @property
    def customizations_path(self) -> Path:
        return self.user_folder / "customizations.json"

    @property
    def user_presets_folder(self) -> Path:
        return self.user_folder / "presets"

    def read_customizations(self) -> dict:
        if not self.customizations_path.exists():
            return {"customCategories": [], "customOptions": [], "deletedBuiltInCategoryIds": []}
        content = read_json(self.customizations_path)
        return {
            "customCategories": content.get("customCategories", []),
            "customOptions": content.get("customOptions", []),
            "deletedBuiltInCategoryIds": content.get("deletedBuiltInCategoryIds", []),
        }

    def write_customizations(self, customizations: dict) -> None:
        write_json(self.customizations_path, {
            "customCategories": customizations.get("customCategories", []),
            "customOptions": customizations.get("customOptions", []),
            "deletedBuiltInCategoryIds": customizations.get("deletedBuiltInCategoryIds", []),
        })

    def read_user_presets(self) -> list:
        if not self.user_presets_folder.is_dir():
            return []
        return [read_json(path) for path in sorted(self.user_presets_folder.glob("*.json"))]

    def save_user_preset(self, ruleset: dict, name: str) -> Path:
        if any(preset["name"] == name for preset in self.shipped_presets):
            raise ValueError(f"'{name}' is a built-in preset; choose another name")
        content = dict(ruleset, name=name, format=RULESET_FORMAT)
        path = self.user_presets_folder / file_name_for(name)
        write_json(path, content)
        return path

    def replace_user_presets(self, presets: list) -> None:
        """Make the user's preset folder hold exactly these presets."""
        self.user_presets_folder.mkdir(parents=True, exist_ok=True)
        wanted_file_names = set()
        for preset in presets:
            file_name = file_name_for(preset["name"])
            wanted_file_names.add(file_name)
            write_json(self.user_presets_folder / file_name, dict(preset, format=RULESET_FORMAT))
        for path in self.user_presets_folder.glob("*.json"):
            if path.name not in wanted_file_names:
                path.unlink()

    def add_custom_option(self, category_id: str, short_name: str, full_text: str) -> str:
        category = self.find_category(category_id)
        if category is None:
            raise ValueError(f"no category '{category_id}'")
        existing_ids = {option["optionId"] for option in category["options"]}
        option_id = unique_id("custom-" + file_name_for(short_name)[:-5], existing_ids)
        customizations = self.read_customizations()
        customizations["customOptions"].append({
            "categoryId": category_id, "optionId": option_id,
            "shortName": short_name, "fullText": full_text,
        })
        self.write_customizations(customizations)
        return option_id

    def add_custom_category(self, category_name: str) -> str:
        existing_ids = {category["categoryId"] for category in self.list_categories()}
        category_id = unique_id("custom-" + file_name_for(category_name)[:-5], existing_ids)
        customizations = self.read_customizations()
        customizations["customCategories"].append(
            {"categoryId": category_id, "categoryName": category_name, "options": []})
        self.write_customizations(customizations)
        return category_id

    def delete_rule(self, category_id: str) -> None:
        """Delete a rule from the catalog for good: the user's own rule (and its options) is
        removed; a built-in rule is hidden from now on. Rulesets that list it skip it."""
        customizations = self.read_customizations()
        own = [c for c in customizations["customCategories"] if c["categoryId"] == category_id]
        if own:
            customizations["customCategories"] = [
                c for c in customizations["customCategories"] if c["categoryId"] != category_id]
            customizations["customOptions"] = [
                o for o in customizations["customOptions"] if o["categoryId"] != category_id]
        elif any(c["categoryId"] == category_id for c in self.shipped_categories):
            if category_id not in customizations["deletedBuiltInCategoryIds"]:
                customizations["deletedBuiltInCategoryIds"].append(category_id)
        else:
            raise KeyError(f"no rule '{category_id}'")
        self.write_customizations(customizations)

    # --- reading -----------------------------------------------------------------------

    def list_categories(self) -> list:
        """Every category, shipped then the user's, each with every option (shipped
        options first, then the user's)."""
        customizations = self.read_customizations()
        deleted = set(customizations["deletedBuiltInCategoryIds"])
        categories = [dict(category, isCustom=False) for category in self.shipped_categories
                      if category["categoryId"] not in deleted]
        categories += [dict(category, isCustom=True) for category in customizations["customCategories"]]
        listed = []
        for category in categories:
            options = [dict(option, isCustom=category["isCustom"]) for option in category["options"]]
            options += [
                dict(option, isCustom=True)
                for option in customizations["customOptions"]
                if option["categoryId"] == category["categoryId"]
            ]
            listed.append(dict(category, options=options))
        return listed

    def find_category(self, category_id: str) -> "dict | None":
        return next((c for c in self.list_categories() if c["categoryId"] == category_id), None)

    def find_option(self, category_id: str, option_id: str) -> "dict | None":
        category = self.find_category(category_id)
        if category is None:
            return None
        return next((o for o in category["options"] if o["optionId"] == option_id), None)

    def list_presets(self) -> list:
        return ([dict(preset, isCustom=False) for preset in self.shipped_presets]
                + [dict(preset, isCustom=True) for preset in self.read_user_presets()])

    def find_preset(self, name: str) -> "dict | None":
        wanted = name.strip().lower()
        return next((p for p in self.list_presets() if p["name"].lower() == wanted), None)


def unique_id(base: str, existing_ids: set) -> str:
    candidate, number = base, 2
    while candidate in existing_ids:
        candidate, number = f"{base}-{number}", number + 1
    return candidate

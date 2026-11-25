/**
 * The page: draws the rule selection state and turns the user's actions into changes
 * of that state. All data lives in RuleSelectionState; this module only renders it.
 */

import { loadShippedCatalog } from "./shipped-catalog-loader.js";
import { CurrentSessionPreferenceStore } from "./preference-stores/current-session-preference-store.js";
import { LocalServerPreferenceStore } from "./preference-stores/local-server-preference-store.js";
import { RuleSelectionState } from "./rule-selection-state.js";
import { makeListReorderableByDragging } from "./drag-to-reorder-list.js";

const NEW_OPTION_MENU_VALUE = "__new-option__";
const EDITED_PRESET_MENU_VALUE = "__edited-preset__";
const TRASH_CAN_ICON =
  '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" ' +
  'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 6h18"/>' +
  '<path d="M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>' +
  '<path d="M10 11v6M14 11v6"/></svg>';
const NEW_CATEGORY_MENU_VALUE = "__new-category__";

/**
 * Launched by the command-line tool, the page is served together with a small API that
 * reports this session's settings. On GitHub Pages (or any plain host) there is no API:
 * customizations last for the session and "Send to local AI agent" stays disabled.
 */
async function readLocalServerSessionSettings() {
  // The tool's server only ever runs on this computer; anywhere else, do not ask.
  if (!["127.0.0.1", "localhost"].includes(location.hostname)) return null;
  try {
    const response = await fetch("api/session-settings");
    if (!response.ok) return null;
    return await response.json();
  } catch {
    return null;
  }
}

// The public web tool (GitHub Pages) points visitors to the agent skill; a copy opened by
// the skill itself does not need to.
document.getElementById("install-skill-link").hidden = !location.hostname.endsWith("github.io");

const shippedCatalog = await loadShippedCatalog();
const localServerSessionSettings = await readLocalServerSessionSettings();

const state = new RuleSelectionState({
  defaultCategories: shippedCatalog.categories,
  defaultPresets: shippedCatalog.presets,
  preferenceStore: localServerSessionSettings
    ? new LocalServerPreferenceStore(localServerSessionSettings.storeFolder)
    : new CurrentSessionPreferenceStore(),
});

const page = {
  presetMenu: document.getElementById("preset-menu"),
  savePresetButton: document.getElementById("save-preset-button"),
  clearRulesButton: document.getElementById("clear-rules-button"),
  ruleList: document.getElementById("rule-list"),
  emptyListNote: document.getElementById("empty-list-note"),
  addRuleMenu: document.getElementById("add-rule-menu"),
  suggestedTopics: document.getElementById("suggested-topics"),
  suggestedTopicChips: document.getElementById("suggested-topic-chips"),
  promptText: document.getElementById("prompt-text"),
  ruleCount: document.getElementById("rule-count"),
  copyButton: document.getElementById("copy-button"),
  storeDescription: document.getElementById("store-description"),
  savePresetDialog: document.getElementById("save-preset-dialog"),
  savePresetForm: document.getElementById("save-preset-form"),
  presetNameInput: document.getElementById("preset-name-input"),
  presetNameNote: document.getElementById("preset-name-note"),
  newCategoryDialog: document.getElementById("new-category-dialog"),
  newCategoryForm: document.getElementById("new-category-form"),
  newCategoryNameInput: document.getElementById("new-category-name-input"),
  toast: document.getElementById("toast"),
};

/** The entry whose "new option" form is open, if any (survives re-rendering). */
let entryIdWithNewOptionFormOpen = null;

/** Entries the user expanded to see and edit their text (all are collapsed by default). */
const expandedEntryIds = new Set();

const createElement = (tagName, properties = {}, children = []) => {
  const element = Object.assign(document.createElement(tagName), properties);
  element.append(...children);
  return element;
};

function showToast(message) {
  page.toast.textContent = message;
  page.toast.classList.add("is-visible");
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => page.toast.classList.remove("is-visible"), 1800);
}

// --- rendering ----------------------------------------------------------------------

/** A copy of the list sorted alphabetically by the given name, ignoring case. */
function sortedByName(items, nameOf) {
  return [...items].sort((a, b) => nameOf(a).localeCompare(nameOf(b), undefined, { sensitivity: "base" }));
}

function renderPresetMenu() {
  const presets = sortedByName(state.listAllPresets(), (preset) => preset.presetName);
  const option = (value, label) => createElement("option", { value, textContent: label });
  const shipped = createElement("optgroup", { label: "Presets" },
    presets.filter((preset) => !preset.isCustom).map((preset) => option(preset.presetName, preset.presetName)));
  const custom = presets.filter((preset) => preset.isCustom);
  // A loaded preset that has been changed shows as "Name*" until it is saved.
  const editedPresetLabel = state.selectedPresetName && state.presetHasUnsavedEdits
    ? [option(EDITED_PRESET_MENU_VALUE, `${state.selectedPresetName}*`)] : [];
  page.presetMenu.replaceChildren(
    option("", "Preset…"),
    ...editedPresetLabel,
    shipped,
    ...(custom.length
      ? [createElement("optgroup", { label: "Your presets" },
          custom.map((preset) => option(preset.presetName, preset.presetName)))]
      : []),
  );
  page.presetMenu.value = editedPresetLabel.length
    ? EDITED_PRESET_MENU_VALUE : (state.selectedPresetName ?? "");
  document.getElementById("unsaved-edits-note").hidden =
    !(state.selectedPresetName && state.presetHasUnsavedEdits);
}

function renderNewOptionForm(entry) {
  const shortNameInput = createElement("input", {
    className: "text-input", placeholder: "Short name, shown in the menu", required: true, maxLength: 60,
  });
  const fullTextInput = createElement("textarea", {
    className: "text-input", placeholder: "The full rule text, as it goes into the prompt", required: true, rows: 4,
  });
  const form = createElement("form", { className: "new-option-form" }, [
    createElement("label", { className: "field-label", textContent: "New option" }),
    shortNameInput,
    fullTextInput,
    createElement("div", { className: "form-actions" }, [
      createElement("button", { type: "button", className: "button button-quiet", textContent: "Cancel",
        onclick: () => { entryIdWithNewOptionFormOpen = null; render(); } }),
      createElement("button", { type: "submit", className: "button button-primary", textContent: "Add option" }),
    ]),
  ]);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const optionId = await state.addCustomOption(
      entry.categoryId, shortNameInput.value.trim(), fullTextInput.value.trim());
    entryIdWithNewOptionFormOpen = null;
    state.chooseOption(entry.entryId, optionId);
    showToast("Option added");
  });
  queueMicrotask(() => shortNameInput.focus());
  return form;
}

function renderEntry(entry, index) {
  const category = state.findCategory(entry.categoryId);
  const option = state.findOption(entry.categoryId, entry.optionId);

  const optionMenu = createElement("select", { className: "select", ariaLabel: `${category.categoryName} option` }, [
    ...sortedByName(category.options, (candidate) => candidate.shortName).map((candidate) =>
      createElement("option", { value: candidate.optionId,
        textContent: candidate.isCustom ? `${candidate.shortName} (yours)` : candidate.shortName })),
    createElement("option", { value: NEW_OPTION_MENU_VALUE, textContent: "＋ New option…" }),
  ]);
  optionMenu.value = entry.optionId ?? NEW_OPTION_MENU_VALUE;
  optionMenu.addEventListener("change", () => {
    if (optionMenu.value === NEW_OPTION_MENU_VALUE) {
      entryIdWithNewOptionFormOpen = entry.entryId;
      render();
    } else {
      entryIdWithNewOptionFormOpen = null;
      state.chooseOption(entry.entryId, optionMenu.value);
    }
  });

  const formIsOpen = entryIdWithNewOptionFormOpen === entry.entryId || !category.options.length;
  // Collapsed by default; an entry whose text was edited stays open so the edit is visible.
  const isExpanded = expandedEntryIds.has(entry.entryId) || state.entryTextIsEdited(entry);

  const isEnabled = entry.enabled !== false;
  const toggle = createElement("input", {
    type: "checkbox", className: "toggle-switch", checked: isEnabled,
    title: isEnabled ? "On — included in the text" : "Off — left out of the text",
    ariaLabel: `${category.categoryName} on or off`,
  });
  toggle.addEventListener("change", () => state.setEntryEnabled(entry.entryId, toggle.checked));

  return createElement("li", { className: isEnabled ? "rule-card" : "rule-card is-off" }, [
    createElement("div", { className: "rule-card-header" }, [
      createElement("button", {
        type: "button", className: "drag-handle", title: "Drag to reorder (or arrow keys)",
        ariaLabel: `Move rule ${index + 1}, ${category.categoryName}`, innerHTML: "<span></span><span></span><span></span>",
      }),
      toggle,
      createElement("span", { className: "rule-category", textContent: category.categoryName }),
      optionMenu,
      createElement("button", {
        type: "button", className: "icon-button remove-button",
        title: "Remove from this preset (it goes back to 'Not added yet')",
        ariaLabel: "Remove from this preset", textContent: "✕",
        onclick: () => state.removeEntry(entry.entryId),
      }),
      // Deleting for good is offered only on an expanded rule, so it is never hit by accident.
      ...(isExpanded ? [
        createElement("button", {
          type: "button", className: "icon-button delete-button",
          title: "Delete this rule for good, everywhere",
          ariaLabel: "Delete this rule for good", innerHTML: TRASH_CAN_ICON,
          onclick: () => confirmAndDeleteRuleForGood(category),
        }),
      ] : []),
      createElement("button", {
        type: "button", className: "icon-button expand-button",
        title: isExpanded ? "Hide the text" : "Show and edit the text",
        ariaLabel: isExpanded ? "Hide the text" : "Show and edit the text",
        ariaExpanded: String(isExpanded),
        textContent: isExpanded ? "▴" : "▾",
        onclick: () => {
          if (isExpanded) expandedEntryIds.delete(entry.entryId);
          else expandedEntryIds.add(entry.entryId);
          render();
        },
      }),
    ]),
    ...(formIsOpen ? [renderNewOptionForm(entry)] : isExpanded ? [renderEditableRuleText(entry)] : []),
  ]);
}

/** The rule's text in an editable field. Once changed: Reset, or save it as a new option. */
function renderEditableRuleText(entry) {
  const field = createElement("textarea", {
    className: "text-input rule-text-field", value: state.textOfEntry(entry) ?? "",
    ariaLabel: "Rule text (editable)", spellcheck: false,
  });
  const fitHeightToText = () => {
    field.style.height = "auto";
    field.style.height = `${field.scrollHeight + 2}px`;
  };
  queueMicrotask(fitHeightToText);

  const shortNameInput = createElement("input", {
    className: "text-input short-name-input", placeholder: "Name for the new option", maxLength: 60,
  });
  const actions = createElement("div", { className: "edited-text-actions" }, [
    createElement("span", { className: "edited-note", textContent: "Edited" }),
    createElement("button", { type: "button", className: "button button-small button-quiet",
      textContent: "Reset", onclick: () => state.resetEntryText(entry.entryId) }),
    shortNameInput,
    createElement("button", { type: "button", className: "button button-small",
      textContent: "Save as new option",
      onclick: async () => {
        const shortName = shortNameInput.value.trim();
        if (!shortName) { shortNameInput.focus(); return; }
        const optionId = await state.addCustomOption(entry.categoryId, shortName, field.value);
        state.chooseOption(entry.entryId, optionId);
        showToast(`Saved “${shortName}”`);
      } }),
  ]);
  const showActionsWhenEdited = () => { actions.hidden = !state.entryTextIsEdited(entry); };
  showActionsWhenEdited();

  field.addEventListener("input", () => {
    state.editEntryText(entry.entryId, field.value);
    fitHeightToText();
    showActionsWhenEdited();
  });
  return createElement("div", { className: "rule-text-block" }, [field, actions]);
}

function renderOutput() {
  renderPresetMenu();
  const text = state.composePromptText();
  page.promptText.textContent = text || "Nothing yet.";
  page.promptText.classList.toggle("is-empty", !text);
  page.copyButton.disabled = !text;
}

async function confirmAndDeleteRuleForGood(category) {
  const consequence = category.isCustom
    ? "It and all of its options will be deleted. This cannot be undone."
    : "This is a built-in rule. It will be hidden for you from now on.";
  const confirmed = confirm(
    `Delete the rule “${category.categoryName}” for good?\n\n`
    + "This is NOT the same as ✕ (remove from this preset). Deleting removes the rule "
    + "everywhere: from every preset, from “Not added yet” and from “Add a rule”.\n\n"
    + consequence);
  if (!confirmed) return;
  await state.deleteRuleFromCatalog(category.categoryId);
  showToast(`Deleted “${category.categoryName}”`);
}

function renderAddRuleMenu() {
  page.addRuleMenu.replaceChildren(
    createElement("option", { value: "", textContent: "＋ Add a rule" }),
    ...sortedByName(state.listAllCategories(), (category) => category.categoryName).map((category) =>
      createElement("option", { value: category.categoryId, textContent: category.categoryName })),
    createElement("option", { value: NEW_CATEGORY_MENU_VALUE, textContent: "＋ New category…" }),
  );
  page.addRuleMenu.value = "";
}

/** Topics not yet in the list, offered as one-tap chips. */
function renderSuggestedTopics() {
  const chosenCategoryIds = new Set(state.chosenEntries.map((entry) => entry.categoryId));
  const suggestions = state.listAllCategories()
    .filter((category) => !chosenCategoryIds.has(category.categoryId) && category.options.length);
  page.suggestedTopics.hidden = suggestions.length === 0;
  page.suggestedTopicChips.replaceChildren(...suggestions.map((category) =>
    createElement("button", {
      type: "button", className: "chip", textContent: `＋ ${category.categoryName}`,
      title: category.options[0].shortName,
      onclick: () => state.addEntry(category.categoryId),
    })));
}

function fitCustomTextFieldToText() {
  const field = document.getElementById("custom-text-field");
  field.style.height = "auto";
  field.style.height = `${field.scrollHeight + 2}px`;
}

function renderCustomText() {
  const field = document.getElementById("custom-text-field");
  if (field.value !== state.customText.text) field.value = state.customText.text;
  document.getElementById("custom-text-toggle").checked = state.customText.enabled;
  document.getElementById("custom-text-placement").value = state.customText.placement;
  document.getElementById("custom-text-block").classList.toggle("is-off", !state.customText.enabled);
  fitCustomTextFieldToText();
}

function render() {
  renderPresetMenu();
  renderCustomText();
  renderSuggestedTopics();
  page.ruleList.replaceChildren(...state.chosenEntries.map(renderEntry));
  page.emptyListNote.hidden = state.chosenEntries.length > 0;
  page.clearRulesButton.disabled = state.chosenEntries.length === 0;
  page.savePresetButton.disabled = state.chosenEntries.length === 0;
  renderAddRuleMenu();
  const text = state.composePromptText();
  page.promptText.textContent = text || "Nothing yet.";
  page.promptText.classList.toggle("is-empty", !text);
  page.copyButton.disabled = !text;
  const count = state.chosenEntries.length;
  const onCount = state.chosenEntries.filter((entry) => entry.enabled !== false).length;
  page.ruleCount.textContent = `${onCount} of ${count} rule${count === 1 ? "" : "s"} on`;
}

// --- actions ------------------------------------------------------------------------

page.presetMenu.addEventListener("change", () => {
  const value = page.presetMenu.value;
  if (!value || value === EDITED_PRESET_MENU_VALUE) return;
  if (state.presetHasUnsavedEdits && !confirm(
    `Load “${value}”? Your unsaved edits to “${state.selectedPresetName}” will be lost.`)) {
    renderPresetMenu();
    return;
  }
  state.applyPreset(value);
  warnAboutRulesTheLoadedPresetPointsAtThatAreGone(value);
});

/** A preset stores settings that point at rules and options; if any of them have been
 * deleted, say so — and for the user's own preset, offer to save it without them. */
async function warnAboutRulesTheLoadedPresetPointsAtThatAreGone(presetName) {
  const missing = state.rulesNotFoundInLastLoadedRuleset || [];
  if (!missing.length) return;
  const list = missing.join(", ");
  if (!state.presetNameIsTheUsersOwn(presetName)) {
    alert(`Warning, these rules were not found: ${list}.\n\n`
      + `They were left out. “${presetName}” is a built-in preset, so it is not changed.`);
    return;
  }
  if (confirm(`Warning, these rules were not found: ${list}.\n\n`
      + `Save “${presetName}” to update this discrepancy?`)) {
    await state.saveChosenEntriesAsPreset(presetName);
    showToast(`Saved “${presetName}” without the missing rules`);
  }
}

page.clearRulesButton.addEventListener("click", () => {
  if (confirm("Clear every rule and the custom text? This cannot be undone (load a preset to start again).")) {
    state.clearEntries();
  }
});
document.getElementById("custom-text-field").addEventListener("input", (event) => {
  state.changeCustomText({ text: event.target.value });
  fitCustomTextFieldToText();
});
document.getElementById("custom-text-clear-button").addEventListener("click", () => {
  const field = document.getElementById("custom-text-field");
  field.value = "";
  state.changeCustomText({ text: "" });
  fitCustomTextFieldToText();
  field.focus();
});
document.getElementById("custom-text-toggle").addEventListener("change", (event) =>
  state.changeCustomText({ enabled: event.target.checked }));
document.getElementById("custom-text-placement").addEventListener("change", (event) =>
  state.changeCustomText({ placement: event.target.value }));
document.getElementById("check-all-button")
  .addEventListener("click", () => state.setAllEntriesEnabled(true));
document.getElementById("uncheck-all-button")
  .addEventListener("click", () => state.setAllEntriesEnabled(false));
document.getElementById("reset-all-text-button").addEventListener("click", () => {
  state.resetAllEntryTexts();
  showToast("All text reset");
});

page.addRuleMenu.addEventListener("change", () => {
  const value = page.addRuleMenu.value;
  if (value === NEW_CATEGORY_MENU_VALUE) {
    page.newCategoryNameInput.value = "";
    page.newCategoryDialog.showModal();
  } else if (value) {
    state.addEntry(value);
  }
  page.addRuleMenu.value = "";
});

page.newCategoryForm.addEventListener("submit", async (event) => {
  if (event.submitter?.value !== "add") return;
  const categoryName = page.newCategoryNameInput.value.trim();
  if (!categoryName) return;
  const categoryId = await state.addCustomCategory(categoryName);
  state.addEntry(categoryId);
  entryIdWithNewOptionFormOpen = state.chosenEntries.at(-1).entryId;
  render();
});

page.savePresetButton.addEventListener("click", () => {
  page.presetNameInput.value = state.selectedPresetName ?? "";
  page.presetNameInput.dispatchEvent(new Event("input"));
  page.savePresetDialog.showModal();
  page.presetNameInput.select();
});

page.presetNameInput.addEventListener("input", () => {
  const name = page.presetNameInput.value.trim();
  page.presetNameNote.textContent = state.presetNameIsShipped(name)
    ? "That name belongs to a built-in preset; choose another."
    : state.listAllPresets().some((preset) => preset.presetName === name)
      ? "This replaces your preset of the same name." : "";
});

page.savePresetForm.addEventListener("submit", async (event) => {
  if (event.submitter?.value !== "save") return;
  const presetName = page.presetNameInput.value.trim();
  if (!presetName || state.presetNameIsShipped(presetName)) {
    event.preventDefault();
    return;
  }
  if (state.presetNameIsTheUsersOwn(presetName)
      && !confirm(`Overwrite your preset “${presetName}”?`)) {
    event.preventDefault();
    return;
  }
  await state.saveChosenEntriesAsPreset(presetName);
  showToast(`Saved “${presetName}”`);
});

page.copyButton.addEventListener("click", async () => {
  const text = state.composePromptText();
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    const range = document.createRange();
    range.selectNodeContents(page.promptText);
    getSelection().removeAllRanges();
    getSelection().addRange(range);
    document.execCommand("copy");
  }
  showToast("Copied to clipboard");
});

makeListReorderableByDragging(page.ruleList, {
  itemSelector: ".rule-card",
  handleSelector: ".drag-handle",
  onMove: (fromIndex, toIndex) => state.moveEntry(fromIndex, toIndex),
});

page.storeDescription.textContent = state.preferenceStore.storeDescription;
state.onChange(render);
state.onEntryTextEdit(renderOutput);
await state.loadSavedCustomizations();
// The address names the loaded preset (?profile=<name>), so a link opens that preset.
const PROFILE_ADDRESS_PARAMETER = "profile";
const profileNamedInAddress = new URLSearchParams(location.search).get(PROFILE_ADDRESS_PARAMETER);
const presetNamedInAddress = profileNamedInAddress && state.listAllPresets()
  .find((preset) => preset.presetName.toLowerCase() === profileNamedInAddress.toLowerCase());

if (localServerSessionSettings?.openedRuleset) {
  state.openRuleset(localServerSessionSettings.openedRuleset);
} else if (presetNamedInAddress) {
  state.applyPreset(presetNamedInAddress.presetName);
} else {
  if (profileNamedInAddress) showToast(`No preset named “${profileNamedInAddress}”`);
  state.applyPreset(shippedCatalog.presetSelectedWhenThePageOpens);
}

function keepTheAddressNamingTheLoadedPreset() {
  const address = new URL(location.href);
  if (state.selectedPresetName) {
    address.searchParams.set(PROFILE_ADDRESS_PARAMETER, state.selectedPresetName);
  } else {
    address.searchParams.delete(PROFILE_ADDRESS_PARAMETER);
  }
  if (address.href !== location.href) history.replaceState(null, "", address);
}
keepTheAddressNamingTheLoadedPreset();
state.onChange(keepTheAddressNamingTheLoadedPreset);

// --- Send to local AI agent ----------------------------------------------------------------

const sendButton = document.getElementById("send-to-agent-button");
if (localServerSessionSettings?.sendToAgentEnabled) {
  sendButton.disabled = false;
  sendButton.title = "Save this ruleset and hand it to the AI agent that opened this page";
  sendButton.addEventListener("click", async () => {
    const response = await fetch("api/send-to-agent", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ruleset: state.exportRuleset(),
        composedText: state.composePromptText(),
      }),
    });
    showToast(response.ok ? "Sent to the AI agent" : "Sending failed");
  });
}

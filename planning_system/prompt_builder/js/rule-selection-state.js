/**
 * The state of one rule selection: which categories and options are available (the
 * shipped catalog plus the user's own additions), the ordered list of chosen rules, and
 * the presets. Holds no knowledge of the page; the page subscribes to changes.
 *
 * A chosen rule ("entry") is {entryId, categoryId, optionId, enabled, editedText}. A rule
 * that is not enabled stays in the list, in its place, but is left out of the text. editedText is
 * null until the user changes the rule's text on the page; then that text is used in
 * place of the option's.
 */

let lastEntryNumber = 0;
const newEntryId = () => `entry-${++lastEntryNumber}`;

const slugFromText = (text) =>
  text.toLowerCase().trim().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "item";

export class RuleSelectionState {
  constructor({ defaultCategories, defaultPresets, preferenceStore }) {
    this.defaultCategories = defaultCategories;
    this.defaultPresets = defaultPresets;
    this.preferenceStore = preferenceStore;
    this.customizations = { customCategories: [], customOptions: [], customPresets: [] };
    this.chosenEntries = [];
    /** Optional free text that turns the ruleset into a specific prompt. */
    this.customText = { text: "", placement: "end", enabled: true };
    /** The preset last loaded (or saved), kept while the user edits it. */
    this.selectedPresetName = null;
    /** The selection as it was when that preset was loaded or saved, to compare with. */
    this.selectionAsSaved = null;
    this.changeListeners = new Set();
    this.textEditListeners = new Set();
  }

  async loadSavedCustomizations() {
    this.customizations = await this.preferenceStore.loadCustomizations();
    this.notifyChange();
  }

  onChange(listener) {
    this.changeListeners.add(listener);
    return () => this.changeListeners.delete(listener);
  }

  notifyChange() {
    for (const listener of this.changeListeners) listener(this);
  }

  async saveCustomizations() {
    await this.preferenceStore.saveCustomizations(this.customizations);
  }

  // --- reading -----------------------------------------------------------------------

  /** Every category, shipped and custom, each with its shipped and custom options. */
  listAllCategories() {
    const categories = [
      ...this.defaultCategories
        .filter((category) => !(this.customizations.deletedBuiltInCategoryIds || [])
          .includes(category.categoryId))
        .map((category) => ({ ...category, isCustom: false })),
      ...this.customizations.customCategories.map((category) => ({ ...category, isCustom: true })),
    ];
    return categories.map((category) => ({
      ...category,
      options: [
        ...category.options.map((option) => ({ ...option, isCustom: category.isCustom })),
        ...this.customizations.customOptions
          .filter((option) => option.categoryId === category.categoryId)
          .map((option) => ({ ...option, isCustom: true })),
      ],
    }));
  }

  findCategory(categoryId) {
    return this.listAllCategories().find((category) => category.categoryId === categoryId);
  }

  findOption(categoryId, optionId) {
    return this.findCategory(categoryId)?.options.find((option) => option.optionId === optionId);
  }

  listAllPresets() {
    return [
      ...this.defaultPresets.map((preset) => ({ ...preset, isCustom: false })),
      ...this.customizations.customPresets.map((preset) => ({ ...preset, isCustom: true })),
    ];
  }

  /** The text to put into a prompt: each chosen rule under its category heading, with the
   * custom text (when on and not empty) at the beginning or the end. */
  composePromptText() {
    const rulesText = this.composeRulesText();
    const customText = this.customText.enabled ? this.customText.text.trim() : "";
    if (!customText) return rulesText;
    if (!rulesText) return customText;
    return this.customText.placement === "start"
      ? `${customText}\n\n${rulesText}`
      : `${rulesText}\n\n${customText}`;
  }

  /** Change the custom text. Text edits do not redraw the page (the field keeps focus);
   * placement and on/off do. */
  changeCustomText(changes) {
    Object.assign(this.customText, changes);
    if ("text" in changes) {
      for (const listener of this.textEditListeners) listener(null);
    } else {
      this.notifyChange();
    }
  }

  composeRulesText() {
    return this.chosenEntries
      .filter((entry) => entry.enabled !== false)
      .map((entry) => {
        const category = this.findCategory(entry.categoryId);
        const text = this.textOfEntry(entry);
        if (!category || text === null) return null;
        return `## ${category.categoryName}\n\n${text}`;
      })
      .filter(Boolean)
      .join("\n\n");
  }

  /** The text an entry contributes: the user's edit, else its option's text. */
  textOfEntry(entry) {
    if (entry.editedText !== null && entry.editedText !== undefined) return entry.editedText;
    return this.findOption(entry.categoryId, entry.optionId)?.fullText ?? null;
  }

  entryTextIsEdited(entry) {
    const option = this.findOption(entry.categoryId, entry.optionId);
    return entry.editedText !== null && entry.editedText !== undefined
      && entry.editedText !== option?.fullText;
  }

  // --- changing the chosen rules -----------------------------------------------------

  /** Change an entry's text while the user types. Listeners are told with the entry id so
   * the page can update the output without redrawing the field being typed in. */
  editEntryText(entryId, text) {
    const entry = this.chosenEntries.find((candidate) => candidate.entryId === entryId);
    if (!entry) return;
    entry.editedText = text;
    for (const listener of this.textEditListeners) listener(entry);
  }

  onEntryTextEdit(listener) {
    this.textEditListeners.add(listener);
  }

  setEntryEnabled(entryId, enabled) {
    const entry = this.chosenEntries.find((candidate) => candidate.entryId === entryId);
    if (!entry) return;
    entry.enabled = enabled;
    this.notifyChange();
  }

  setAllEntriesEnabled(enabled) {
    for (const entry of this.chosenEntries) entry.enabled = enabled;
    this.notifyChange();
  }

  resetAllEntryTexts() {
    for (const entry of this.chosenEntries) entry.editedText = null;
    this.notifyChange();
  }

  resetEntryText(entryId) {
    const entry = this.chosenEntries.find((candidate) => candidate.entryId === entryId);
    if (!entry) return;
    entry.editedText = null;
    this.notifyChange();
  }

  addEntry(categoryId) {
    const category = this.findCategory(categoryId);
    if (!category) return;
    this.chosenEntries.push({
      entryId: newEntryId(),
      categoryId,
      optionId: category.options[0]?.optionId ?? null,
      enabled: true,
      editedText: null,
    });
    this.notifyChange();
  }

  removeEntry(entryId) {
    this.chosenEntries = this.chosenEntries.filter((entry) => entry.entryId !== entryId);
    this.notifyChange();
  }

  chooseOption(entryId, optionId) {
    const entry = this.chosenEntries.find((candidate) => candidate.entryId === entryId);
    if (!entry) return;
    entry.optionId = optionId;
    entry.editedText = null;
    this.notifyChange();
  }

  moveEntry(fromIndex, toIndex) {
    if (fromIndex === toIndex) return;
    const [moved] = this.chosenEntries.splice(fromIndex, 1);
    this.chosenEntries.splice(toIndex, 0, moved);
    this.notifyChange();
  }

  /** Clear the list and let go of the loaded preset: a cleared list is a fresh start,
   * not an edit of that preset. */
  clearEntries() {
    this.chosenEntries = [];
    this.customText = { ...this.customText, text: "" };
    this.selectedPresetName = null;
    this.rememberSelectionAsSaved();
    this.notifyChange();
  }

  applyPreset(presetName) {
    const preset = this.listAllPresets().find((candidate) => candidate.presetName === presetName);
    if (!preset) return;
    this.loadRuleset(preset);
    this.selectedPresetName = presetName;
    this.rememberSelectionAsSaved();
    this.notifyChange();
  }

  /** Make a ruleset (a preset or a saved instance: {entries, customText}) the current
   * selection. Every category is always shown: those the ruleset does not use follow it,
   * switched off. Does not notify; callers do. */
  loadRuleset(ruleset) {
    // A ruleset stores settings that point at rules and options in the catalog. Any it
    // points at that are no longer there are left out, and listed for the caller.
    this.rulesNotFoundInLastLoadedRuleset = (ruleset.entries || [])
      .filter((entry) => !this.findOption(entry.categoryId, entry.optionId))
      .map((entry) => {
        const category = this.findCategory(entry.categoryId);
        if (category) return `${category.categoryName} (option “${entry.optionId}”)`;
        // A deleted built-in rule still has its name in the shipped catalog.
        const deletedBuiltIn = this.defaultCategories.find((c) => c.categoryId === entry.categoryId);
        return deletedBuiltIn ? deletedBuiltIn.categoryName : entry.categoryId;
      });
    this.chosenEntries = (ruleset.entries || [])
      .filter((entry) => this.findOption(entry.categoryId, entry.optionId))
      .map((entry) => ({
        entryId: newEntryId(),
        categoryId: entry.categoryId,
        optionId: entry.optionId,
        enabled: entry.enabled !== false,
        editedText: entry.editedText ?? null,
      }));
    this.customText = {
      text: ruleset.customText?.text ?? "",
      placement: ruleset.customText?.placement ?? "end",
      enabled: ruleset.customText?.enabled ?? true,
    };
    this.selectedPresetName = null;
    this.rememberSelectionAsSaved();
  }

  openRuleset(ruleset) {
    this.loadRuleset(ruleset);
    this.notifyChange();
  }

  /** The current selection as a ruleset file's content (the same shape presets use). */
  exportRuleset(name) {
    return {
      format: "ai-prompt-builder/ruleset@1",
      name: name || this.selectedPresetName || "Untitled",
      entries: this.chosenEntries
        .filter((entry) => entry.optionId)
        .map((entry) => ({
          categoryId: entry.categoryId,
          optionId: entry.optionId,
          enabled: entry.enabled !== false,
          editedText: this.entryTextIsEdited(entry) ? entry.editedText : null,
        })),
      customText: { ...this.customText },
    };
  }

  // --- the user's own additions ------------------------------------------------------

  async addCustomOption(categoryId, shortName, fullText) {
    const category = this.findCategory(categoryId);
    const existingIds = new Set(category.options.map((option) => option.optionId));
    let optionId = `custom-${slugFromText(shortName)}`;
    for (let number = 2; existingIds.has(optionId); number++) {
      optionId = `custom-${slugFromText(shortName)}-${number}`;
    }
    this.customizations.customOptions.push({ categoryId, optionId, shortName, fullText });
    await this.saveCustomizations();
    this.notifyChange();
    return optionId;
  }

  /** Delete a rule from the catalog for good: the user's own rule (and its options) is
   * removed; a built-in rule is hidden from now on. It also leaves the current list. */
  async deleteRuleFromCatalog(categoryId) {
    const isOwn = this.customizations.customCategories.some((c) => c.categoryId === categoryId);
    if (isOwn) {
      this.customizations.customCategories =
        this.customizations.customCategories.filter((c) => c.categoryId !== categoryId);
      this.customizations.customOptions =
        this.customizations.customOptions.filter((o) => o.categoryId !== categoryId);
    } else {
      this.customizations.deletedBuiltInCategoryIds = [
        ...(this.customizations.deletedBuiltInCategoryIds || []), categoryId];
    }
    this.chosenEntries = this.chosenEntries.filter((entry) => entry.categoryId !== categoryId);
    await this.saveCustomizations();
    this.notifyChange();
  }

  async addCustomCategory(categoryName) {
    const existingIds = new Set(this.listAllCategories().map((category) => category.categoryId));
    let categoryId = `custom-${slugFromText(categoryName)}`;
    for (let number = 2; existingIds.has(categoryId); number++) {
      categoryId = `custom-${slugFromText(categoryName)}-${number}`;
    }
    this.customizations.customCategories.push({ categoryId, categoryName, options: [] });
    await this.saveCustomizations();
    this.notifyChange();
    return categoryId;
  }

  /** Save the chosen rules, in order, as a preset. A custom preset of the same name is replaced. */
  async saveChosenEntriesAsPreset(presetName) {
    const entries = this.chosenEntries
      .filter((entry) => entry.optionId)
      .map((entry) => ({
        categoryId: entry.categoryId,
        optionId: entry.optionId,
        enabled: entry.enabled !== false,
        editedText: this.entryTextIsEdited(entry) ? entry.editedText : null,
      }));
    this.customizations.customPresets = [
      ...this.customizations.customPresets.filter((preset) => preset.presetName !== presetName),
      { presetName, entries, customText: { ...this.customText } },
    ];
    this.rememberSelectionAsSaved();
    this.selectedPresetName = presetName;
    await this.saveCustomizations();
    this.notifyChange();
  }

  /** What is compared to tell whether the loaded preset has been changed: every rule's
   * order, option, on/off and edited text, and the custom text. */
  describeSelectionForComparison() {
    const { entries, customText } = this.exportRuleset();
    return JSON.stringify({ entries, customText });
  }

  rememberSelectionAsSaved() {
    this.selectionAsSaved = this.describeSelectionForComparison();
  }

  /** True when the selection differs from the preset as it was loaded or last saved —
   * so undoing a change makes it false again. */
  get presetHasUnsavedEdits() {
    return Boolean(this.selectedPresetName)
      && this.describeSelectionForComparison() !== this.selectionAsSaved;
  }

  presetNameIsTheUsersOwn(presetName) {
    return this.customizations.customPresets.some((preset) => preset.presetName === presetName);
  }

  presetNameIsShipped(presetName) {
    return this.defaultPresets.some((preset) => preset.presetName === presetName);
  }
}

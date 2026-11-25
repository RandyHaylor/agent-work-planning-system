/**
 * A preference store that keeps the user's customizations (their own options, their own
 * categories and their saved presets) for the current browser session only.
 *
 * Every preference store has the same interface, so the page never needs to know where
 * customizations live. A later store (for example one backed by a file in the user's
 * Google Drive, after Google sign-in) only has to implement these methods:
 *
 *   storeDescription: string                      — shown to the user ("Saved for this session")
 *   async loadCustomizations()  -> customizations  — EMPTY_CUSTOMIZATIONS when none
 *   async saveCustomizations(customizations)       — replaces what is stored
 *
 * customizations = {
 *   customCategories: [{categoryId, categoryName, options: []}],
 *   customOptions:    [{categoryId, optionId, shortName, fullText}],
 *   customPresets:    [{presetName, entries: [{categoryId, optionId}]}]
 * }
 */

export const EMPTY_CUSTOMIZATIONS = Object.freeze({
  customCategories: [],
  customOptions: [],
  customPresets: [],
  deletedBuiltInCategoryIds: [],
});

export class CurrentSessionPreferenceStore {
  constructor() {
    this.storeDescription = "Your own options and presets last until this tab closes. Saving them comes later.";
    this.customizationsKeptInMemory = structuredClone(EMPTY_CUSTOMIZATIONS);
  }

  async loadCustomizations() {
    return structuredClone(this.customizationsKeptInMemory);
  }

  async saveCustomizations(customizations) {
    this.customizationsKeptInMemory = structuredClone(customizations);
  }
}

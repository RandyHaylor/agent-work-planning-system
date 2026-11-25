/**
 * A preference store that keeps the user's customizations on the computer running the
 * page's local server (started by the command-line tool), as JSON files in the user's
 * prompt-builder folder. Same interface as every preference store (see
 * current-session-preference-store.js).
 */

import { EMPTY_CUSTOMIZATIONS } from "./current-session-preference-store.js";

export class LocalServerPreferenceStore {
  constructor(storeFolderDescription) {
    this.storeDescription = `Your own options and presets are saved in ${storeFolderDescription}.`;
  }

  async loadCustomizations() {
    const response = await fetch("api/customizations");
    if (!response.ok) return structuredClone(EMPTY_CUSTOMIZATIONS);
    return response.json();
  }

  async saveCustomizations(customizations) {
    const response = await fetch("api/customizations", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(customizations),
    });
    if (!response.ok) throw new Error(`saving failed: ${response.status}`);
  }
}

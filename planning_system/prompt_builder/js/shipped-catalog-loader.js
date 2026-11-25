/**
 * Reads the shipped rule categories and presets from the shared JSON files in data/ —
 * the same files the command-line tool reads, so the page and the tool always agree.
 *
 *   data/rule-categories.json   {categories: [{categoryId, categoryName, options: [...]}]}
 *   data/presets/index.json     {presetSelectedWhenThePageOpens, presetFiles: [...]}
 *   data/presets/<name>.json    a ruleset: {name, entries, customText}
 */

async function readJson(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`could not read ${url}: ${response.status}`);
  return response.json();
}

export async function loadShippedCatalog(dataFolderUrl = "data/") {
  const [categoryFile, presetIndex] = await Promise.all([
    readJson(`${dataFolderUrl}rule-categories.json`),
    readJson(`${dataFolderUrl}presets/index.json`),
  ]);
  const presetFiles = await Promise.all(
    presetIndex.presetFiles.map((fileName) => readJson(`${dataFolderUrl}presets/${fileName}`)));
  return {
    categories: categoryFile.categories,
    presets: presetFiles.map((ruleset) => ({
      presetName: ruleset.name,
      entries: ruleset.entries,
      customText: ruleset.customText,
    })),
    presetSelectedWhenThePageOpens: presetIndex.presetSelectedWhenThePageOpens,
  };
}

#!/usr/bin/env node
'use strict';

let fs = null;
try {
  fs = require('node:fs');
} catch (_) {
  fs = null;
}

let __SHOW_APP_LOG = false;

function log(msg) {
  if (!__SHOW_APP_LOG) return;
  if (typeof process !== 'undefined' && process.stderr && process.stderr.write) {
    process.stderr.write(`${msg}\n`);
  } else if (typeof console !== 'undefined' && console.log) {
    console.log(msg);
  }
}

function progress(message) {
  log(message);
}

class CliError extends Error {}

function normalizeTerms(values) {
  return values.map((value) => String(value).toLowerCase());
}

function createDefaultConfig() {
  return {
    sourceJson: null,
    output: 'txt',
    showSchema: false,
    searchKeys: [],
    searchVals: [],
    showSearchHitSubTrees: false,
    excludeFieldsMatching: [],
    excludeFieldsContaining: [],
    truncateLineLength: null,
    truncateKeyLength: null,
    truncateValueLength: null,
    truncateObjectNameLength: null,
    showLineNumbers: true,
    indentSize: 2,
    showStats: false,
    showNodeIndexes: false,
    showFullAddresses: false,
    showChildCounts: false,
    showNodePathSteps: [],
    maxRenderDepth: null,
    hideLiteralSubstrings: [],
  };
}

function normalizeConfig(overrides = {}) {
  const config = { ...createDefaultConfig(), ...overrides };

  config.output = config.output || 'txt';
  config.searchKeys = normalizeTerms(config.searchKeys || []);
  config.searchVals = normalizeTerms(config.searchVals || []);
  config.excludeFieldsMatching = (config.excludeFieldsMatching || []).map(String);
  config.excludeFieldsContaining = normalizeTerms(config.excludeFieldsContaining || []);
  config.showSearchHitSubTrees = Boolean(config.showSearchHitSubTrees);
  config.showSchema = Boolean(config.showSchema);
  config.showStats = Boolean(config.showStats);
  config.showNodeIndexes = Boolean(config.showNodeIndexes);
  config.showFullAddresses = Boolean(config.showFullAddresses);
  config.showChildCounts = Boolean(config.showChildCounts);
  config.hideLiteralSubstrings = Array.isArray(config.hideLiteralSubstrings)
    ? config.hideLiteralSubstrings.filter((substring) => typeof substring === 'string' && substring.length > 0)
    : [];
  config.showNodePathSteps = Array.isArray(config.showNodePathSteps) ? config.showNodePathSteps.map((step) => {
    const parsedStep = Number.parseInt(step, 10);
    if (Number.isNaN(parsedStep) || parsedStep < 0) {
      throw new CliError(`invalid step in --show-node path: ${step}`);
    }
    return parsedStep;
  }) : [];
  if (config.maxRenderDepth !== null && config.maxRenderDepth !== undefined && config.maxRenderDepth !== '') {
    config.maxRenderDepth = Number.parseInt(config.maxRenderDepth, 10);
    if (Number.isNaN(config.maxRenderDepth) || config.maxRenderDepth < 0) {
      throw new CliError('invalid value for --depth');
    }
  } else {
    config.maxRenderDepth = null;
  }

  if (config.output === 'json') {
    config.showLineNumbers = false;
    // truncateLineLength is ALLOWED in json mode — it breaks strict
    // JSON validity, but exposes a type silhouette (first char of each
    // value reveals the type) which is useful for large-file scanning.
  } else {
    config.showLineNumbers = typeof config.showLineNumbers === 'boolean' ? config.showLineNumbers : true;
  }

  if (config.truncateLineLength !== null && config.truncateLineLength !== undefined && config.truncateLineLength !== '') {
    config.truncateLineLength = Number.parseInt(config.truncateLineLength, 10);
    if (Number.isNaN(config.truncateLineLength)) {
      throw new CliError('invalid value for truncateLineLength');
    }
  } else {
    config.truncateLineLength = null;
  }

  // Normalize each of the three per-class truncation limits. -1 (or any
  // negative number) means "do not truncate this class". Any non-negative
  // integer is a character cap. Null/undefined/empty also mean no cap.
  const normalizeOptionalTruncationLimit = (rawValue, settingLabel) => {
    if (rawValue === null || rawValue === undefined || rawValue === '') return null;
    const parsedLimit = Number.parseInt(rawValue, 10);
    if (Number.isNaN(parsedLimit)) throw new CliError(`invalid value for ${settingLabel}`);
    return parsedLimit < 0 ? null : parsedLimit;
  };
  config.truncateKeyLength = normalizeOptionalTruncationLimit(config.truncateKeyLength, 'truncateKeyLength');
  config.truncateValueLength = normalizeOptionalTruncationLimit(config.truncateValueLength, 'truncateValueLength');
  config.truncateObjectNameLength = normalizeOptionalTruncationLimit(config.truncateObjectNameLength, 'truncateObjectNameLength');

  if (config.indentSize !== null && config.indentSize !== undefined && config.indentSize !== '') {
    config.indentSize = Number.parseInt(config.indentSize, 10);
    if (Number.isNaN(config.indentSize)) {
      throw new CliError('invalid value for indentSize');
    }
  } else {
    config.indentSize = 2;
  }

  validateArgs(config);
  return config;
}

function parseArgs(argv) {
  const config = createDefaultConfig();

  const takeList = (args, index) => {
    const values = [];
    let i = index;
    while (i < args.length && !args[i].startsWith('--')) {
      values.push(args[i]);
      i += 1;
    }
    if (values.length === 0) {
      throw new CliError(`missing value(s) for ${args[index - 1]}`);
    }
    return { values, nextIndex: i };
  };

  let i = 0;
  while (i < argv.length) {
    const arg = argv[i];

    if (!arg.startsWith('--')) {
      if (config.sourceJson !== null) {
        throw new CliError(`unexpected positional argument: ${arg}`);
      }
      config.sourceJson = arg;
      i += 1;
      continue;
    }

    switch (arg) {
      case '--output':
        i += 1;
        if (!argv[i] || argv[i].startsWith('--')) throw new CliError('missing value for --output');
        if (!['txt', 'csv', 'json'].includes(argv[i])) throw new CliError('invalid value for --output');
        config.output = argv[i];
        i += 1;
        break;
      case '--show-schema':
        config.showSchema = true;
        i += 1;
        break;
      case '--search-keys': {
        i += 1;
        const { values, nextIndex } = takeList(argv, i);
        config.searchKeys = normalizeTerms(values);
        i = nextIndex;
        break;
      }
      case '--search-vals': {
        i += 1;
        const { values, nextIndex } = takeList(argv, i);
        config.searchVals = normalizeTerms(values);
        i = nextIndex;
        break;
      }
      case '--show-search-hit-sub-trees':
        config.showSearchHitSubTrees = true;
        i += 1;
        break;
      case '--exclude-fields-matching': {
        i += 1;
        const { values, nextIndex } = takeList(argv, i);
        config.excludeFieldsMatching = values;
        i = nextIndex;
        break;
      }
      case '--exclude-fields-containing': {
        i += 1;
        const { values, nextIndex } = takeList(argv, i);
        config.excludeFieldsContaining = normalizeTerms(values);
        i = nextIndex;
        break;
      }
      case '--truncate-line-length':
        i += 1;
        if (!argv[i] || argv[i].startsWith('--')) throw new CliError('missing value for --truncate-line-length');
        config.truncateLineLength = Number.parseInt(argv[i], 10);
        if (Number.isNaN(config.truncateLineLength)) throw new CliError('invalid value for --truncate-line-length');
        i += 1;
        break;
      case '--hide-line-numbers':
        config.showLineNumbers = false;
        i += 1;
        break;
      case '--show-app-log':
        i += 1;
        break;
      case '--show-stats':
        config.showStats = true;
        i += 1;
        break;
      case '--show-node-indexes':
        config.showNodeIndexes = true;
        i += 1;
        break;
      case '--show-child-counts':
        config.showChildCounts = true;
        i += 1;
        break;
      case '--hide': {
        i += 1;
        const { values, nextIndex } = takeList(argv, i);
        config.hideLiteralSubstrings = values;
        i = nextIndex;
        break;
      }
      case '--truncate-key-val-obj': {
        i += 1;
        if (argv[i] === undefined || argv[i + 1] === undefined || argv[i + 2] === undefined) {
          throw new CliError('--truncate-key-val-obj requires three integer values (key-limit val-limit obj-limit); use -1 for "no truncation"');
        }
        const parseSinglePerClassTruncationLimit = (rawValue, classLabel) => {
          const parsedLimit = Number.parseInt(rawValue, 10);
          if (Number.isNaN(parsedLimit)) throw new CliError(`invalid ${classLabel} limit for --truncate-key-val-obj: ${rawValue}`);
          return parsedLimit < 0 ? null : parsedLimit;
        };
        config.truncateKeyLength = parseSinglePerClassTruncationLimit(argv[i], 'key');
        config.truncateValueLength = parseSinglePerClassTruncationLimit(argv[i + 1], 'val');
        config.truncateObjectNameLength = parseSinglePerClassTruncationLimit(argv[i + 2], 'obj');
        i += 3;
        break;
      }
      case '--show-full-addresses':
        config.showFullAddresses = true;
        i += 1;
        break;
      case '--show-node': {
        i += 1;
        if (!argv[i] || argv[i].startsWith('--')) throw new CliError('missing value for --show-node');
        const pathString = argv[i];
        config.showNodePathSteps = pathString.split('-').map((step) => {
          const parsedStep = Number.parseInt(step, 10);
          if (Number.isNaN(parsedStep) || parsedStep < 0) {
            throw new CliError(`invalid step in --show-node path: ${step}`);
          }
          return parsedStep;
        });
        i += 1;
        break;
      }
      case '--depth':
        i += 1;
        if (!argv[i] || argv[i].startsWith('--')) throw new CliError('missing value for --depth');
        config.maxRenderDepth = Number.parseInt(argv[i], 10);
        if (Number.isNaN(config.maxRenderDepth) || config.maxRenderDepth < 0) throw new CliError('invalid value for --depth');
        i += 1;
        break;
      case '--indent-size':
        i += 1;
        if (!argv[i] || argv[i].startsWith('--')) throw new CliError('missing value for --indent-size');
        config.indentSize = Number.parseInt(argv[i], 10);
        if (Number.isNaN(config.indentSize)) throw new CliError('invalid value for --indent-size');
        i += 1;
        break;
      default:
        throw new CliError(`unknown argument: ${arg}`);
    }
  }

  if (!config.sourceJson) {
    throw new CliError('missing source_json');
  }

  validateArgs(config);
  return config;
}

function validateArgs(config) {
  if (!config.showSchema) return;
  const incompatible = [
    config.output !== 'txt',
    config.searchKeys.length > 0,
    config.searchVals.length > 0,
    config.showSearchHitSubTrees,
    config.excludeFieldsMatching.length > 0,
    config.excludeFieldsContaining.length > 0,
    config.truncateLineLength !== null,
    config.truncateKeyLength !== null,
    config.truncateValueLength !== null,
    config.truncateObjectNameLength !== null,
    !config.showLineNumbers,
    config.indentSize !== 2,
    config.showStats,
    config.showNodeIndexes,
    config.showFullAddresses,
    config.showNodePathSteps.length > 0,
    config.maxRenderDepth !== null,
    config.hideLiteralSubstrings.length > 0,
  ];
  if (incompatible.some(Boolean)) {
    throw new CliError('--show-schema not compatible with other arguments');
  }
}

function isScalar(value) {
  return !Array.isArray(value) && (value === null || typeof value !== 'object');
}

function scalarToText(value) {
  if (value === null) return 'null';
  if (value === true) return 'true';
  if (value === false) return 'false';
  return String(value);
}

class MatchRules {
  constructor(config) {
    this.config = config;
  }

  searchActive() {
    return this.config.searchKeys.length > 0 || this.config.searchVals.length > 0;
  }

  keyMatches(key) {
    const folded = key.toLowerCase();
    return this.config.searchKeys.some((term) => folded.includes(term));
  }

  valueMatches(value) {
    if (!isScalar(value)) return false;
    const folded = scalarToText(value).toLowerCase();
    return this.config.searchVals.some((term) => folded.includes(term));
  }

  excludeKey(key) {
    return this.config.excludeFieldsMatching.includes(key)
      || this.config.excludeFieldsContaining.some((term) => key.toLowerCase().includes(term));
  }
}

class SearchAnalyzer {
  constructor(config) {
    this.rules = new MatchRules(config);
  }

  analyze(value, label = null) {
    if (!this.rules.searchActive()) {
      return { relevant: true, directMatch: true, hitCount: 0 };
    }

    const ownMatch = (label !== null && this.rules.keyMatches(label)) || this.rules.valueMatches(value);
    const children = this.childInfos(value);
    const childHitCount = children.reduce((sum, info) => sum + info.hitCount, 0);
    const childRelevant = children.some((info) => info.relevant);
    return {
      relevant: ownMatch || childRelevant,
      directMatch: ownMatch,
      hitCount: (ownMatch ? 1 : 0) + childHitCount,
    };
  }

  childInfos(value) {
    if (Array.isArray(value)) {
      return value.map((item) => this.analyze(item, null));
    }
    if (value && typeof value === 'object') {
      return Object.entries(value).map(([key, child]) => this.analyze(child, key));
    }
    return [];
  }
}

function node(label, valueText = null, children = []) {
  return { label, valueText, children };
}

class NodeBuilder {
  constructor(config) {
    this.config = config;
    this.rules = new MatchRules(config);
    this.analyzer = new SearchAnalyzer(config);
  }

  build(value, label = null) {
    const info = this.analyzer.analyze(value, label);
    return this.buildNode(value, label, info);
  }

  buildNode(value, label, info) {
    if (!info.relevant) return null;

    if (label !== null && this.rules.excludeKey(label)) {
      return null;
    }

    if (isScalar(value)) {
      return label === null ? node(scalarToText(value)) : node(label, scalarToText(value));
    }

    const children = this.buildChildren(value, info);
    if (label === null) {
      return children.length > 0 ? node(null, null, children) : null;
    }
    if (children.length > 0) {
      return node(label, null, children);
    }
    if (info.directMatch) {
      return node(label);
    }
    return null;
  }

  includeAllVisibleDescendants(info) {
    if (!this.rules.searchActive()) return true;
    return info.directMatch && this.config.showSearchHitSubTrees;
  }

  buildChildren(value, info) {
    const children = [];
    const includeAll = this.includeAllVisibleDescendants(info);
    const items = Array.isArray(value)
      ? value.map((child, index) => [`[${index}]`, child])
      : Object.entries(value);

    for (const [childLabel, childValue] of items) {
      const childInfo = this.analyzer.analyze(childValue, childLabel);
      const includeChild = includeAll || !this.rules.searchActive() || childInfo.relevant;
      if (!includeChild) continue;
      const childNode = includeAll
        ? this.buildVisibleSubtree(childValue, childLabel)
        : this.buildNode(childValue, childLabel, childInfo);
      if (childNode && hasContent(childNode)) {
        children.push(childNode);
      }
    }
    return children;
  }

  buildVisibleSubtree(value, label) {
    if (label !== null && this.rules.excludeKey(label)) {
      return null;
    }
    if (isScalar(value)) {
      return label === null ? node(scalarToText(value)) : node(label, scalarToText(value));
    }

    const items = Array.isArray(value)
      ? value.map((child, index) => [`[${index}]`, child])
      : Object.entries(value);
    const children = [];
    for (const [childLabel, childValue] of items) {
      const childNode = this.buildVisibleSubtree(childValue, childLabel);
      if (childNode && hasContent(childNode)) {
        children.push(childNode);
      }
    }
    if (label === null) {
      return children.length > 0 ? node(null, null, children) : null;
    }
    return children.length > 0 ? node(label, null, children) : node(label);
  }
}

function hasContent(treeNode) {
  return treeNode.valueText !== null || treeNode.children.length > 0;
}

class TextRenderer {
  render(context) {
    const lines = this.buildLines(context.tree, context.config);
    const finalLines = context.config.output === 'txt'
      ? applyTextLineRules(lines, context.config)
      : lines;
    return finalLines.join('\n');
  }

  buildLines(tree, config) {
    if (!tree) return ['<no matches>'];
    const indentSize = config.indentSize;
    const showNodeIndexes = config.showNodeIndexes;
    const showFullAddresses = config.showFullAddresses;
    const showChildCounts = config.showChildCounts;
    const showAnyAddressPrefix = showNodeIndexes || showFullAddresses;
    const maxRenderDepth = config.maxRenderDepth; // null or a non-negative integer
    const lines = [];

    const walk = (treeNode, depth, siblingIndexOrNull, accumulatedAddressSteps) => {
      const hasLabel = treeNode.label !== null && treeNode.label !== '';
      if (hasLabel) {
        const indent = ' '.repeat(depth * indentSize);
        let addressPrefix = '';
        if (showFullAddresses) {
          addressPrefix = `[${accumulatedAddressSteps.join('-')}] `;
        } else if (showNodeIndexes && siblingIndexOrNull !== null) {
          addressPrefix = `[${siblingIndexOrNull}] `;
        }
        // When address prefixing is on and the label is a bare array
        // index like "[0]", the prefix already carries the same info — drop
        // the label text to avoid "[0] [0]" duplication.
        const labelLooksLikeArrayIndex = isArrayIndexLabel(treeNode.label);
        const labelWithClassTruncation = applyLabelClassTruncation(treeNode.label, treeNode, config);
        const labelForRendering = showAnyAddressPrefix && labelLooksLikeArrayIndex ? '' : labelWithClassTruncation;
        const valueTextWithClassTruncation = applyValueClassTruncation(treeNode.valueText, config);
        const childCountSuffix = (showChildCounts && treeNode.valueText === null && treeNode.children.length > 0)
          ? ` (${treeNode.children.length} child${treeNode.children.length === 1 ? '' : 'ren'})`
          : '';
        if (labelForRendering === '' && treeNode.valueText === null) {
          lines.push(`${indent}${addressPrefix.trimEnd()}${childCountSuffix}`);
        } else if (treeNode.valueText !== null) {
          lines.push(`${indent}${addressPrefix}${labelForRendering}${labelForRendering ? ': ' : ''}${valueTextWithClassTruncation}`);
        } else {
          lines.push(`${indent}${addressPrefix}${labelForRendering}${childCountSuffix}`);
        }
      }
      const nextDepth = (treeNode.label === null || treeNode.label === '') ? depth : depth + 1;
      if (maxRenderDepth !== null && nextDepth > maxRenderDepth) {
        return;
      }
      for (let childIndex = 0; childIndex < treeNode.children.length; childIndex++) {
        walk(treeNode.children[childIndex], nextDepth, childIndex, [...accumulatedAddressSteps, childIndex]);
      }
    };
    walk(tree, 0, null, []);
    return lines.length > 0 ? lines : ['<no matches>'];
  }
}

function truncateText(text, maxLen) {
  if (text.length <= maxLen) return text;
  if (maxLen <= 0) return '';
  if (maxLen === 1) return '…';
  return `${text.slice(0, maxLen - 1)}…`;
}

function isArrayIndexLabel(label) {
  return typeof label === 'string' && /^\[\d+\]$/.test(label);
}

function applyLabelClassTruncation(label, treeNode, config) {
  // Labels that are array positional indexes (e.g. "[12]") are never
  // truncated — they are positional identifiers, not names.
  if (label === null || label === undefined || label === '') return label;
  if (isArrayIndexLabel(label)) return label;
  const labelPointsAtScalar = treeNode.valueText !== null;
  const classLimit = labelPointsAtScalar ? config.truncateKeyLength : config.truncateObjectNameLength;
  if (classLimit === null) return label;
  return truncateText(label, classLimit);
}

function applyValueClassTruncation(valueText, config) {
  if (valueText === null || valueText === undefined) return valueText;
  if (config.truncateValueLength === null) return valueText;
  return truncateText(valueText, config.truncateValueLength);
}

function applyTextLineRules(lines, config) {
  const truncated = config.truncateLineLength === null
    ? lines
    : lines.map((line) => truncateText(line, config.truncateLineLength));
  if (!config.showLineNumbers) return truncated;
  const width = String(truncated.length).length;
  return truncated.map((line, index) => `${String(index + 1).padStart(width, ' ')} | ${line}`);
}

function childrenAreArrayish(children) {
  return children.length > 0 && children.every((child) => (child.label || '').startsWith('['));
}

class JsonRenderer {
  render(context) {
    let renderedOutput;
    if (context.config.showNodeIndexes) {
      // Destructive / visual-only mode: emit JSON-shaped text with [N]
      // sibling-index prefixes inline. The result is NOT valid JSON — it
      // is meant for reading and copy-pasting addresses, not for piping
      // into downstream JSON consumers.
      renderedOutput = this.renderJsonShapedWithVisualIndexes(context.tree, context.config);
    } else {
      const payload = this.project(context.tree, context.config);
      renderedOutput = JSON.stringify(payload, null, 2);
    }
    // Optional line truncation. Also destructive — breaks strict JSON
    // validity — but collapses each line to a type silhouette:
    // the first character after "key": (", {, [, digit, t, f, n)
    // reveals the value's JSON type without reading the whole value.
    if (context.config.truncateLineLength !== null) {
      renderedOutput = renderedOutput
        .split('\n')
        .map((singleLine) => truncateText(singleLine, context.config.truncateLineLength))
        .join('\n');
    }
    return renderedOutput;
  }

  project(tree, config) {
    if (!tree) return null;
    if (tree.label === null || tree.label === '') {
      if (tree.children.length === 0) return null;
      return Object.fromEntries(tree.children.map((child) => [this.truncatedChildLabel(child, config), this.payload(child, config)]));
    }
    return { [this.truncatedChildLabel(tree, config)]: this.payload(tree, config) };
  }

  truncatedChildLabel(childTreeNode, config) {
    return applyLabelClassTruncation(childTreeNode.label, childTreeNode, config);
  }

  payload(treeNode, config) {
    if (treeNode.valueText !== null) return applyValueClassTruncation(treeNode.valueText, config);
    if (treeNode.children.length === 0) return null;
    if (childrenAreArrayish(treeNode.children)) {
      return treeNode.children.map((child) => this.payload(child, config));
    }
    return Object.fromEntries(treeNode.children.map((child) => [this.truncatedChildLabel(child, config), this.payload(child, config)]));
  }

  renderJsonShapedWithVisualIndexes(tree, config) {
    if (!tree) return 'null';
    const indentUnit = ' '.repeat(config.indentSize || 2);
    const maxRenderDepth = config.maxRenderDepth;
    return this.renderValueFromTreeNodeWithVisualIndexes(tree, indentUnit, '', 0, maxRenderDepth, config);
  }

  renderValueFromTreeNodeWithVisualIndexes(treeNode, indentUnit, currentIndent, currentDepth, maxRenderDepth, config) {
    if (treeNode.valueText !== null && treeNode.children.length === 0) {
      return JSON.stringify(applyValueClassTruncation(treeNode.valueText, config));
    }
    if (treeNode.children.length === 0) {
      return 'null';
    }
    if (maxRenderDepth !== null && currentDepth > maxRenderDepth) {
      return '"..."';
    }
    const childrenLookLikeArray = childrenAreArrayish(treeNode.children);
    const deeperIndent = currentIndent + indentUnit;
    const renderedChildren = treeNode.children.map((childNode, siblingIndex) => {
      const childValue = this.renderValueFromTreeNodeWithVisualIndexes(childNode, indentUnit, deeperIndent, currentDepth + 1, maxRenderDepth, config);
      if (childrenLookLikeArray) {
        return `${deeperIndent}[${siblingIndex}] ${childValue}`;
      }
      const childLabelAfterClassTruncation = applyLabelClassTruncation(childNode.label, childNode, config);
      return `${deeperIndent}[${siblingIndex}] ${JSON.stringify(childLabelAfterClassTruncation)}: ${childValue}`;
    });
    if (childrenLookLikeArray) {
      return `[\n${renderedChildren.join(',\n')}\n${currentIndent}]`;
    }
    return `{\n${renderedChildren.join(',\n')}\n${currentIndent}}`;
  }
}

class CsvRenderer {
  render(context) {
    const rows = this.collectRows(context.tree);
    const rendered = rows.map((row) => row.map((cell) => this.truncateCell(cell, context.config.truncateLineLength)));
    return rendered
      .map((row, index) => this.writeCsvRow(context.config.showLineNumbers ? [String(index + 1), ...row] : row))
      .join('\n');
  }

  collectRows(tree) {
    if (!tree) return [];
    const rows = [];
    const walk = (treeNode, path) => {
      const currentPath = (treeNode.label === null || treeNode.label === '') ? path : [...path, treeNode.label];
      if (treeNode.valueText !== null) {
        rows.push([...currentPath, treeNode.valueText]);
        return;
      }
      if (treeNode.label !== null && treeNode.label !== '' && treeNode.children.length === 0) {
        rows.push(currentPath);
        return;
      }
      for (const child of treeNode.children) {
        walk(child, currentPath);
      }
    };
    walk(tree, []);
    return rows;
  }

  truncateCell(cell, maxLen) {
    if (maxLen === null) return cell;
    return truncateText(cell, maxLen);
  }

  escapeCell(cell) {
    if (/[",\n\r]/.test(cell)) {
      return `"${cell.replace(/"/g, '""')}"`;
    }
    return cell;
  }

  writeCsvRow(row) {
    return row.map((cell) => this.escapeCell(cell)).join(',');
  }
}

class SchemaRenderer {
  render(context) {
    return JSON.stringify(this.schema(context.rawJson), null, 2);
  }

  schema(value) {
    if (Array.isArray(value)) {
      return [value.length > 0 ? this.schema(value[0]) : 'empty-array'];
    }
    if (value && typeof value === 'object') {
      return Object.fromEntries(Object.entries(value).map(([key, child]) => [key, this.schema(child)]));
    }
    if (value === null) return 'null';
    if (typeof value === 'string') return 'string';
    if (typeof value === 'number') return 'number';
    if (typeof value === 'boolean') return 'boolean';
    return typeof value;
  }
}

function createRenderer(config) {
  if (config.showSchema) return new SchemaRenderer();
  if (config.output === 'json') return new JsonRenderer();
  if (config.output === 'csv') return new CsvRenderer();
  return new TextRenderer();
}

class Pipeline {
  constructor(stages) {
    this.stages = stages;
  }

  run(context) {
    let current = context;
    for (const stage of this.stages) {
      current = stage.run(current);
    }
    return current;
  }
}

function parseJsonDocumentOrJsonLines(rawText) {
  // Always build an array of parsed records. For a regular JSON file, we
  // push one entry. For a JSONL file, we push one entry per line. Callers
  // can inspect records.length to decide whether to unwrap.
  const parsedRecords = [];
  try {
    parsedRecords.push(JSON.parse(rawText));
    return { records: parsedRecords, isJsonLines: false };
  } catch (primaryJsonParseError) {
    const lines = rawText.split(/\r?\n/);
    for (let lineIndex = 0; lineIndex < lines.length; lineIndex++) {
      const trimmedLine = lines[lineIndex].trim();
      if (trimmedLine === '') continue;
      try {
        parsedRecords.push(JSON.parse(trimmedLine));
      } catch (_) {
        throw primaryJsonParseError;
      }
    }
    if (parsedRecords.length < 2) {
      throw primaryJsonParseError;
    }
    return { records: parsedRecords, isJsonLines: true };
  }
}

class ParseJsonStage {
  run(context) {
    progress('performing parse...');
    if (!fs) {
      throw new CliError('file access not available in this runtime');
    }
    context.rawText = fs.readFileSync(context.config.sourceJson, 'utf8');
    const { records, isJsonLines } = parseJsonDocumentOrJsonLines(context.rawText);
    context.isJsonLines = isJsonLines;
    // Parse always yields an array of documents. A single-element array
    // (regular JSON file, or a JSONL with exactly one record) is unwrapped
    // so the output does not show a meaningless [0] wrapper. Two or more
    // records stay as an array so each document gets its own index.
    context.rawJson = records.length === 1 ? records[0] : records;
    progress(`parse complete: 1 file loaded (${records.length} document${records.length === 1 ? '' : 's'}${isJsonLines ? ', JSON Lines' : ''})`);
    return context;
  }
}

function getOrderedChildEntries(parentValue) {
  // Uniform addressing: both arrays and objects expose their children as an
  // ordered list of [stepIndex, childValue] pairs. Array items are addressed
  // by their natural index; object key/value pairs are addressed by the
  // insertion-order position of the key.
  if (Array.isArray(parentValue)) {
    return parentValue.map((childValue, stepIndex) => [stepIndex, childValue]);
  }
  if (parentValue && typeof parentValue === 'object') {
    return Object.values(parentValue).map((childValue, stepIndex) => [stepIndex, childValue]);
  }
  return [];
}

class DrillToNodePathStage {
  run(context) {
    const pathSteps = context.config.showNodePathSteps;
    if (!pathSteps || pathSteps.length === 0) return context;
    progress(`performing drill to node path: ${pathSteps.join('-')}`);
    let currentValue = context.rawJson;
    for (let depthIndex = 0; depthIndex < pathSteps.length; depthIndex++) {
      const requestedStep = pathSteps[depthIndex];
      const childEntries = getOrderedChildEntries(currentValue);
      if (requestedStep >= childEntries.length) {
        throw new CliError(
          `--show-node step out of range at depth ${depthIndex}: asked for index ${requestedStep}, but this node only has ${childEntries.length} child${childEntries.length === 1 ? '' : 'ren'}`
        );
      }
      currentValue = childEntries[requestedStep][1];
    }
    context.rawJson = currentValue;
    progress('drill complete');
    return context;
  }
}

function computeJsonStats(rawJson, rawText) {
  let totalObjects = 0;
  let totalArrays = 0;
  let nestingDepth = 0;
  const walk = (value, depth) => {
    if (depth > nestingDepth) nestingDepth = depth;
    if (Array.isArray(value)) {
      totalArrays += 1;
      for (const item of value) walk(item, depth + 1);
    } else if (value && typeof value === 'object') {
      totalObjects += 1;
      for (const child of Object.values(value)) walk(child, depth + 1);
    }
  };
  walk(rawJson, 1);
  const totalCharCount = typeof rawText === 'string' && rawText.length > 0
    ? rawText.length
    : JSON.stringify(rawJson).length;
  return { totalCharCount, nestingDepth, totalObjects, totalArrays, jsonValid: true };
}

class StatsDecorationStage {
  run(context) {
    if (!context.config.showStats) return context;
    progress('performing stats decoration...');
    const stats = computeJsonStats(context.rawJson, context.rawText);
    context.stats = stats;
    if (context.config.output === 'json') {
      let parsedOutput;
      try {
        parsedOutput = context.outputText && context.outputText.length > 0
          ? JSON.parse(context.outputText)
          : null;
      } catch (_) {
        parsedOutput = null;
      }
      const wrapped = { jsonStats: stats, ...(parsedOutput && typeof parsedOutput === 'object' && !Array.isArray(parsedOutput) ? parsedOutput : { output: parsedOutput }) };
      context.outputText = JSON.stringify(wrapped, null, 2);
    } else {
      const statsLines = [
        `total char count: ${stats.totalCharCount}`,
        `nesting depth: ${stats.nestingDepth}`,
        `total objects: ${stats.totalObjects}`,
        `total arrays: ${stats.totalArrays}`,
        `json-valid: ${stats.jsonValid}`,
      ];
      context.outputText = `${statsLines.join('\n')}\n${context.outputText}`;
    }
    progress('stats decoration complete');
    return context;
  }
}

class SearchReportStage {
  run(context) {
    progress('performing search analysis...');
    const analyzer = new SearchAnalyzer(context.config);
    context.searchInfo = analyzer.analyze(context.rawJson);
    if (analyzer.rules.searchActive()) {
      progress(`search analysis complete: ${context.searchInfo.hitCount} hit(s) found`);
    } else {
      progress('search analysis complete: full document mode');
    }
    return context;
  }
}

class BuildTreeStage {
  run(context) {
    progress('performing tree build...');
    const builder = new NodeBuilder(context.config);
    context.tree = builder.build(context.rawJson);
    const topLevelCount = context.tree ? context.tree.children.length : 0;
    progress(`tree build complete: ${topLevelCount} top-level node(s)`);
    return context;
  }
}

class RenderStage {
  run(context) {
    progress('performing render...');
    context.outputText = createRenderer(context.config).render(context);
    const lineCount = context.outputText ? context.outputText.split(/\r?\n/).length : 0;
    progress(`render complete: ${lineCount} line(s) produced`);
    return context;
  }
}

class HideLiteralSubstringsStage {
  run(context) {
    const substringsToHide = context.config.hideLiteralSubstrings;
    if (!substringsToHide || substringsToHide.length === 0) return context;
    progress(`performing hide-literal substitution for ${substringsToHide.length} pattern(s)`);
    let filteredOutput = context.outputText || '';
    for (const substring of substringsToHide) {
      filteredOutput = filteredOutput.split(substring).join('');
    }
    context.outputText = filteredOutput;
    progress('hide-literal substitution complete');
    return context;
  }
}

function defaultPipeline() {
  return new Pipeline([
    new ParseJsonStage(),
    new DrillToNodePathStage(),
    new SearchReportStage(),
    new BuildTreeStage(),
    new RenderStage(),
    new StatsDecorationStage(),
    new HideLiteralSubstringsStage(),
  ]);
}

function memoryPipeline() {
  return new Pipeline([
    new DrillToNodePathStage(),
    new SearchReportStage(),
    new BuildTreeStage(),
    new RenderStage(),
    new StatsDecorationStage(),
    new HideLiteralSubstringsStage(),
  ]);
}

function runWithValue(rawJson, configOverrides = {}) {
  __SHOW_APP_LOG = false;
  const config = normalizeConfig(configOverrides);
  const context = { config, rawJson, searchInfo: null, tree: null, outputText: '', rawText: null, stats: null };
  return memoryPipeline().run(context);
}

function runWithJsonText(jsonText, configOverrides = {}) {
  __SHOW_APP_LOG = false;
  const { records } = parseJsonDocumentOrJsonLines(jsonText);
  const rawJson = records.length === 1 ? records[0] : records;
  return runWithValue(rawJson, configOverrides);
}

function runCli(argv = process.argv.slice(2)) {
  __SHOW_APP_LOG = argv.includes('--show-app-log');
  try {
    const config = parseArgs(argv);
    const context = { config, rawJson: null, searchInfo: null, tree: null, outputText: '', rawText: null, stats: null };
    const result = defaultPipeline().run(context);
    process.stdout.write(`${result.outputText}\n`);
    return 0;
  } catch (error) {
    if (error instanceof CliError) {
      process.stderr.write(`${error.message}\n`);
      return 2;
    }
    if (error instanceof SyntaxError) {
      process.stderr.write(`invalid JSON: ${error.message}\n`);
      return 1;
    }
    if (error && error.code === 'ENOENT') {
      process.stderr.write(`file not found: ${error.message}\n`);
      return 1;
    }
    process.stderr.write(`${error.stack || error.message}\n`);
    return 1;
  }
}

const exportedApi = {
  runCli,
  parseArgs,
  defaultPipeline,
  normalizeConfig,
  runWithValue,
  runWithJsonText,
};

if (typeof module !== 'undefined' && module.exports) {
  module.exports = exportedApi;
}

if (typeof window !== 'undefined') {
  window.QuickJsonReader = exportedApi;
}

if (typeof require !== 'undefined' && typeof module !== 'undefined' && require.main === module) {
  process.exitCode = runCli();
}

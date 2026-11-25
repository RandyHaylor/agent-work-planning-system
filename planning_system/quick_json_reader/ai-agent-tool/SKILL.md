---
name: quick-json-reader
description: Deterministic JSON inspection and extraction tool for humans and AI agents.
tools:
  - node
  - cli
  - json
---

## Purpose

Quickly inspect, search, and extract structured JSON data with minimal cognitive overhead.

Supports both:
- full inspection of JSON data
- targeted extraction of relevant content

## Runtime Environments

This tool uses one JavaScript engine in:

- Node.js for CLI and agent execution
- Browser JavaScript for a static web app

The core behavior should remain identical across environments.

## Core Model

Pipeline:

1. Parse JSON
2. Search (identify relevant branches)
3. Exclude (remove selected fields entirely)
4. Prune (remove empty containers)
5. Render (txt, csv, json)

Rules:

- Search determines relevance
- Exclude removes fields from output entirely
- Output is deterministic

## Tool Interface

CLI:
- `node quick_json_reader.js file.json ...`

Browser:
- `QuickJsonReader.runWithJsonText(jsonText, config)`
- `QuickJsonReader.runWithValue(value, config)`

Output:
- Text (default)
- CSV (RFC-compliant)
- JSON (structured projection)
- Schema (standalone inferred structure)

Flags control:
- search scope
- visibility
- output format
- truncation

## When to Use

Use this tool when:

- JSON is large or deeply nested
- you need to locate specific values or keys
- logs contain noise or sensitive fields
- structured extraction is required
- output must be machine-consumable

## Key Patterns

Find values:

```bash
node quick_json_reader.js file.json --search-vals error timeout failed
```

Locate structures:

```bash
node quick_json_reader.js file.json --search-keys user profile session
```

Expand context:

```bash
node quick_json_reader.js file.json --include-search-children
```

Remove noise:

```bash
node quick_json_reader.js file.json --exclude-fields-matching token password secret
```

```bash
node quick_json_reader.js file.json --exclude-fields-containing debug internal temp
```

Combine search + exclude:

```bash
node quick_json_reader.js file.json --search-vals user123 --exclude-fields-matching token --output json
```

Inspect structure:

```bash
node quick_json_reader.js file.json --show-schema
```

Constraints:
- `--show-schema` must be used alone
- outputs inferred structure, not formal JSON Schema

## Efficiency Guidelines

- Start with `--search-vals` to reduce scope
- Add `--include-search-children` only when necessary
- Use exclude rules aggressively to remove noise
- Prefer CSV for tabular extraction
- Prefer JSON for chaining tools

## Agent Optimization

Prefer:
- JSON output when chaining tools
- CSV output for structured extraction
- minimal flags to reduce output size

Avoid:
- truncation when machine parsing is required
- combining `--show-schema` with other flags

## Output Selection

| Goal | Output |
|------|--------|
| human inspection | txt |
| structured analysis | csv |
| automation / pipelines | json |
| structure discovery | schema |

## Summary

This tool provides:

- deterministic JSON inspection
- controlled visibility
- flexible output formats
- compatibility with human and automated workflows

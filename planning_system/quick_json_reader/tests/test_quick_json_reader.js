const test = require('node:test');
const assert = require('node:assert/strict');
const { spawnSync } = require('node:child_process');
const path = require('node:path');
const mod = require('../src/quick_json_reader.js');

const CLI_PATH = path.join(__dirname, '..', 'src', 'quick_json_reader.js');
const SAMPLE_INPUT_PATH = path.join(__dirname, '..', 'examples', 'sample_easy_json_reader_input.json');

const sample = {
  user: {
    name: 'alice',
    token: 'abc123',
    nested: { secret: 'hidden_value' }
  },
  system: { status: 'ok' }
};

test('supports in-memory text rendering', () => {
  const result = mod.runWithValue(sample, { output: 'txt' });
  assert.match(result.outputText, /user/);
  assert.match(result.outputText, /alice/);
});

test('supports json output without line numbers', () => {
  const result = mod.runWithValue(sample, { output: 'json', showLineNumbers: true });
  assert.doesNotMatch(result.outputText, /\|/);
  assert.match(result.outputText, /"user"/);
});

test('enforces schema isolation', () => {
  assert.throws(
    () => mod.runWithValue(sample, { showSchema: true, searchVals: ['alice'] }),
    /--show-schema not compatible with other arguments/
  );
});

test('exclude fully removes matching branch from output', () => {
  const result = mod.runWithValue(sample, {
    output: 'txt',
    excludeFieldsMatching: ['nested']
  });
  assert.match(result.outputText, /user/);
  assert.doesNotMatch(result.outputText, /nested/);
  assert.doesNotMatch(result.outputText, /secret/);
  assert.doesNotMatch(result.outputText, /hidden_value/);
});

test('exclude works with containing-match on scalar fields', () => {
  const result = mod.runWithValue(sample, {
    output: 'txt',
    excludeFieldsContaining: ['tok']
  });
  assert.match(result.outputText, /name/);
  assert.doesNotMatch(result.outputText, /token/);
  assert.doesNotMatch(result.outputText, /abc123/);
});

test('CLI accepts --exclude-fields-matching and omits the field', () => {
  const result = spawnSync('node', [CLI_PATH, SAMPLE_INPUT_PATH, '--exclude-fields-matching', 'password', 'token'], { encoding: 'utf8' });
  assert.equal(result.status, 0);
  assert.doesNotMatch(result.stdout, /password/);
  assert.doesNotMatch(result.stdout, /token/);
  assert.doesNotMatch(result.stdout, /\[hidden\]/);
});

test('parseArgs accepts --show-app-log flag', () => {
  assert.doesNotThrow(() => mod.parseArgs(['some-file.json', '--show-app-log']));
});

test('CLI is silent on stderr by default', () => {
  const result = spawnSync('node', [CLI_PATH, SAMPLE_INPUT_PATH], { encoding: 'utf8' });
  assert.equal(result.status, 0);
  assert.equal(result.stderr, '');
  assert.match(result.stdout, /user/);
});

test('CLI emits progress logs to stderr with --show-app-log', () => {
  const result = spawnSync('node', [CLI_PATH, SAMPLE_INPUT_PATH, '--show-app-log'], { encoding: 'utf8' });
  assert.equal(result.status, 0);
  assert.match(result.stderr, /performing parse/);
  assert.match(result.stderr, /render complete/);
  assert.match(result.stdout, /user/);
});

test('showStats prepends stat lines to txt output', () => {
  const result = mod.runWithValue(sample, { output: 'txt', showStats: true });
  const lines = result.outputText.split('\n');
  assert.match(lines[0], /^total char count: \d+$/);
  assert.match(lines[1], /^nesting depth: \d+$/);
  assert.match(lines[2], /^total objects: \d+$/);
  assert.match(lines[3], /^total arrays: \d+$/);
  assert.equal(lines[4], 'json-valid: true');
});

test('showStats in json output yields valid json with jsonStats first', () => {
  const result = mod.runWithValue(sample, { output: 'json', showStats: true });
  const parsed = JSON.parse(result.outputText);
  const firstKey = Object.keys(parsed)[0];
  assert.equal(firstKey, 'jsonStats');
  assert.equal(parsed.jsonStats.jsonValid, true);
  assert.equal(typeof parsed.jsonStats.totalCharCount, 'number');
  assert.equal(typeof parsed.jsonStats.nestingDepth, 'number');
  assert.equal(typeof parsed.jsonStats.totalObjects, 'number');
  assert.equal(typeof parsed.jsonStats.totalArrays, 'number');
  assert.ok('user' in parsed);
});

test('CLI --show-stats prepends stats to txt stdout', () => {
  const result = spawnSync('node', [CLI_PATH, SAMPLE_INPUT_PATH, '--show-stats'], { encoding: 'utf8' });
  assert.equal(result.status, 0);
  const lines = result.stdout.split('\n');
  assert.match(lines[0], /^total char count: \d+$/);
  assert.match(lines[4], /^json-valid: true$/);
});

test('CLI --show-stats --output json yields valid json starting with jsonStats', () => {
  const result = spawnSync('node', [CLI_PATH, SAMPLE_INPUT_PATH, '--show-stats', '--output', 'json'], { encoding: 'utf8' });
  assert.equal(result.status, 0);
  const parsed = JSON.parse(result.stdout);
  assert.equal(Object.keys(parsed)[0], 'jsonStats');
  assert.equal(parsed.jsonStats.jsonValid, true);
});

test('--show-schema cannot be combined with --show-stats', () => {
  assert.throws(
    () => mod.parseArgs(['file.json', '--show-schema', '--show-stats']),
    /not compatible/
  );
});

test('runWithJsonText auto-detects JSON Lines and wraps records into an array', () => {
  const jsonLinesText = [
    '{"id":1,"type":"login","status":"ok"}',
    '{"id":2,"type":"purchase","status":"failed"}',
    '{"id":3,"type":"logout","status":"ok"}',
  ].join('\n');
  const result = mod.runWithJsonText(jsonLinesText, { output: 'json', showStats: true });
  const parsed = JSON.parse(result.outputText);
  // 3 records -> 3 top-level JSONL objects (totalObjects >= 3) + 1 wrapper array
  assert.equal(parsed.jsonStats.totalArrays >= 1, true);
  assert.ok(parsed.jsonStats.totalObjects >= 3);
});

test('runWithJsonText preserves single-document JSON behavior', () => {
  const result = mod.runWithJsonText('{"user": {"name": "alice"}}', { output: 'json' });
  const parsed = JSON.parse(result.outputText);
  assert.equal(parsed.user.name, 'alice');
});

test('CLI auto-detects JSONL file and produces valid stats', () => {
  const fs = require('node:fs');
  const jsonlFixturePath = '/tmp/integration_test_jsonl_fixture.jsonl';
  fs.writeFileSync(jsonlFixturePath, [
    '{"event":"start","ok":true}',
    '{"event":"middle","ok":true}',
    '{"event":"end","ok":false}',
    '',
  ].join('\n'));
  const result = spawnSync('node', [CLI_PATH, jsonlFixturePath, '--show-stats', '--output', 'json'], { encoding: 'utf8' });
  assert.equal(result.status, 0);
  const parsed = JSON.parse(result.stdout);
  assert.equal(parsed.jsonStats.totalObjects, 3);
});

test('showNodeIndexes prefixes each txt line with local sibling index', () => {
  const result = mod.runWithValue(sample, { output: 'txt', showNodeIndexes: true, showLineNumbers: false });
  assert.match(result.outputText, /^\[0\] user/m);
  assert.match(result.outputText, /^\s+\[0\] name: alice/m);
  assert.match(result.outputText, /^\s+\[2\] nested/m);
});

test('maxRenderDepth caps how deep text output walks', () => {
  const deepSample = { a: { b: { c: { d: 'leaf' } } } };
  const resultAtDepth0 = mod.runWithValue(deepSample, { output: 'txt', showLineNumbers: false, maxRenderDepth: 0 });
  assert.match(resultAtDepth0.outputText, /^a$/m);
  assert.doesNotMatch(resultAtDepth0.outputText, /\bleaf\b/);
  const resultAtDepth2 = mod.runWithValue(deepSample, { output: 'txt', showLineNumbers: false, maxRenderDepth: 2 });
  assert.match(resultAtDepth2.outputText, /\ba\b/);
  assert.match(resultAtDepth2.outputText, /\bc\b/);
  assert.doesNotMatch(resultAtDepth2.outputText, /\bleaf\b/);
});

test('showNodePathSteps drills to a nested subtree by sibling indexes', () => {
  const nestedSample = { alpha: { beta: { gamma: 'deep' } }, other: 'ignored' };
  // alpha is the 0th child; beta is the 0th child of alpha; gamma is the 0th child of beta.
  const result = mod.runWithValue(nestedSample, { output: 'txt', showLineNumbers: false, showNodePathSteps: [0, 0] });
  assert.match(result.outputText, /gamma: deep/);
  assert.doesNotMatch(result.outputText, /ignored/);
});

test('showNodePathSteps step out of range throws a clear error', () => {
  assert.throws(
    () => mod.runWithValue({ only: 'one child' }, { showNodePathSteps: [99] }),
    /--show-node step out of range/
  );
});

test('showFullAddresses prefixes each line with the complete path from root', () => {
  const result = mod.runWithValue(sample, { output: 'txt', showFullAddresses: true, showLineNumbers: false });
  assert.match(result.outputText, /^\[0\] user/m);
  assert.match(result.outputText, /^\s+\[0-0\] name: alice/m);
  assert.match(result.outputText, /^\s+\[0-2\] nested/m);
  assert.match(result.outputText, /^\s+\[0-2-0\] secret:/m);
});

test('CLI --show-node-indexes with --output json produces visual-only indexed output', () => {
  const fs = require('node:fs');
  const visualJsonFixturePath = '/tmp/integration_test_visual_json_fixture.json';
  fs.writeFileSync(visualJsonFixturePath, JSON.stringify({ a: { b: 1 }, c: [true, false] }));
  const result = spawnSync('node', [CLI_PATH, visualJsonFixturePath, '--show-node-indexes', '--output', 'json'], { encoding: 'utf8' });
  assert.equal(result.status, 0);
  assert.match(result.stdout, /\[0\] "a":/);
  assert.match(result.stdout, /\[1\] "c":/);
  // NOTE: this output is intentionally not valid JSON — do not JSON.parse it.
  assert.throws(() => JSON.parse(result.stdout));
});

test('hideLiteralSubstrings strips each literal from the rendered output', () => {
  const urlSample = { api: 'https://example.com/x', docs: 'https://example.com/y' };
  const result = mod.runWithValue(urlSample, {
    output: 'txt',
    showLineNumbers: false,
    hideLiteralSubstrings: ['https://', 'example.com'],
  });
  assert.doesNotMatch(result.outputText, /https:\/\//);
  assert.doesNotMatch(result.outputText, /example\.com/);
  assert.match(result.outputText, /\/x/);
  assert.match(result.outputText, /\/y/);
});

test('runWithValue does not emit to stderr even if gate was previously on', () => {
  const chunks = [];
  const originalWrite = process.stderr.write.bind(process.stderr);
  process.stderr.write = (chunk) => {
    chunks.push(String(chunk));
    return true;
  };
  try {
    mod.runWithValue(sample, { output: 'txt' });
  } finally {
    process.stderr.write = originalWrite;
  }
  assert.equal(chunks.join(''), '');
});

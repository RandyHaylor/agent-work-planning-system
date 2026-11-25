const test = require('node:test');
const assert = require('node:assert/strict');
const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');

const CLI_PATH = path.join(__dirname, '..', 'src', 'quick_json_reader.js');
const STDIN_RUNNER_PATH = path.join(__dirname, '..', 'src', 'stdin_runner.js');
const SAMPLE_INPUT_PATH = path.join(__dirname, '..', 'examples', 'sample_easy_json_reader_input.json');

function runStdin(text, argv) {
  return spawnSync('node', [STDIN_RUNNER_PATH], { input: JSON.stringify({ text, argv }), encoding: 'utf8' });
}

test('stdin runner output equals runCli on a file with the same content', () => {
  const flags = ['--show-full-addresses', '--depth', '2'];
  const fromFile = spawnSync('node', [CLI_PATH, SAMPLE_INPUT_PATH, ...flags], { encoding: 'utf8' });
  const fromStdin = runStdin(fs.readFileSync(SAMPLE_INPUT_PATH, 'utf8'), flags);
  assert.equal(fromStdin.status, 0);
  assert.equal(fromStdin.stdout, fromFile.stdout);
});

test('stdin runner exits 2 on bad flags', () => {
  const result = runStdin('{"a": 1}', ['--no-such-flag']);
  assert.equal(result.status, 2);
  assert.match(result.stderr, /unknown argument/);
});

test('stdin runner exits 1 on invalid JSON text', () => {
  const result = runStdin('{not json', []);
  assert.equal(result.status, 1);
});

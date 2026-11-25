#!/usr/bin/env node
'use strict';
// Reads {"text": "<json or jsonl>", "argv": ["--flag", ...]} from stdin, runs quick_json_reader on the
// text in memory and writes its output to stdout. No files, no temp dirs. Exit codes as runCli:
// 0 ok, 2 usage error (bad flags), 1 invalid JSON input.

const { parseArgs, runWithJsonText } = require('./quick_json_reader.js');

const STDIN_PLACEHOLDER_SOURCE = '<stdin>';

function runStdinRequest(requestText) {
  let request;
  try {
    request = JSON.parse(requestText);
  } catch (error) {
    return { exitCode: 2, stdout: '', stderr: `invalid stdin request: ${error.message}\n` };
  }
  try {
    const config = parseArgs([STDIN_PLACEHOLDER_SOURCE, ...(request.argv || [])]);
    const result = runWithJsonText(String(request.text ?? ''), config);
    return { exitCode: 0, stdout: `${result.outputText}\n`, stderr: '' };
  } catch (error) {
    if (error && error.constructor && error.constructor.name === 'CliError') {
      return { exitCode: 2, stdout: '', stderr: `${error.message}\n` };
    }
    if (error instanceof SyntaxError) {
      return { exitCode: 1, stdout: '', stderr: `invalid JSON: ${error.message}\n` };
    }
    return { exitCode: 1, stdout: '', stderr: `${error.stack || error.message}\n` };
  }
}

module.exports = { runStdinRequest };

if (require.main === module) {
  const chunks = [];
  process.stdin.on('data', (chunk) => chunks.push(chunk));
  process.stdin.on('end', () => {
    const outcome = runStdinRequest(Buffer.concat(chunks).toString('utf8'));
    process.stdout.write(outcome.stdout);
    process.stderr.write(outcome.stderr);
    process.exitCode = outcome.exitCode;
  });
}

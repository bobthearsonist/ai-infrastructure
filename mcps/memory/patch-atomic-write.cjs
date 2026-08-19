#!/usr/bin/env node
/**
 * Build-time patch: make @modelcontextprotocol/server-memory's saveGraph() atomic.
 *
 * Upstream saveGraph() truncate-writes the ENTIRE graph on every mutation:
 *     await fs.writeFile(this.memoryFilePath, lines.join("\n"));
 * A crash mid-write truncates the store; concurrent writers interleave.
 * There is no lock/flock/mutex anywhere in the package.
 *
 * This rewrites it to write-temp-then-rename. The temp name is per-PID on
 * purpose: a SHARED temp path still corrupts, because two writers racing on
 * one source path let writer A rename writer B's half-written bytes into
 * place. rename(2) is atomic within a filesystem, so a reader sees either the
 * old file or the new one -- never a truncated one.
 *
 * FAILS THE BUILD (exit 1) if the anchor is not found. A patch that silently
 * no-ops after an upstream refactor is worse than no patch at all: you would
 * ship an unprotected writer believing it was fixed.
 */
'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { execSync } = require('node:child_process');

const PKG = '@modelcontextprotocol/server-memory';

const ANCHOR = '        await fs.writeFile(this.memoryFilePath, lines.join("\\n"));';

const REPLACEMENT = [
  '        const tmp = `${this.memoryFilePath}.tmp.${process.pid}`;',
  '        await fs.writeFile(tmp, lines.join("\\n"));',
  '        await fs.rename(tmp, this.memoryFilePath);',
].join('\n');

const PATCH_MARKER = 'await fs.rename(tmp, this.memoryFilePath);';

function fail(msg) {
  console.error('');
  console.error('  PATCH FAILED: ' + msg);
  console.error('  Refusing to build an image with a non-atomic memory writer.');
  console.error('');
  process.exit(1);
}

// Resolve the install location instead of hardcoding it.
let target = process.argv[2];
if (!target) {
  let globalRoot;
  try {
    globalRoot = execSync('npm root -g', { encoding: 'utf8' }).trim();
  } catch (err) {
    fail('could not run `npm root -g`: ' + err.message);
  }
  target = path.join(globalRoot, ...PKG.split('/'), 'dist', 'index.js');
}

if (!fs.existsSync(target)) {
  fail('target file does not exist: ' + target);
}

const original = fs.readFileSync(target, 'utf8');

if (original.includes(PATCH_MARKER)) {
  console.log('  patch-atomic-write: already patched, nothing to do -> ' + target);
  process.exit(0);
}

const occurrences = original.split(ANCHOR).length - 1;
if (occurrences !== 1) {
  fail(
    'expected exactly 1 occurrence of the saveGraph anchor in ' + target +
    ', found ' + occurrences + '. Upstream likely refactored saveGraph(); ' +
    're-derive the anchor before building.'
  );
}

const patched = original.replace(ANCHOR, REPLACEMENT);

if (!patched.includes(PATCH_MARKER)) {
  fail('post-replacement verification failed: rename() not present.');
}
if (patched === original) {
  fail('post-replacement verification failed: file content unchanged.');
}

fs.writeFileSync(target, patched, 'utf8');

// Re-read from disk so we verify what actually landed, not what we think we wrote.
const readback = fs.readFileSync(target, 'utf8');
if (!readback.includes(PATCH_MARKER) || !readback.includes('.tmp.${process.pid}')) {
  fail('readback verification failed: patch did not persist to ' + target);
}

console.log('  patch-atomic-write: saveGraph() is now atomic (tmp + rename) -> ' + target);

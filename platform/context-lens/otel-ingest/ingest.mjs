// Imports Claude Code's raw API body logs (OTEL_LOG_RAW_API_BODIES=file:<dir>)
// into Context Lens, so sessions can be captured without pointing
// ANTHROPIC_BASE_URL at the proxy (which disables Remote Control).
//
// Claude Code appends one line per successful request to <dir>/index.jsonl,
// naming a request file and a response file. This loop follows that index by
// byte offset, posts each pair to /api/ingest, and deletes the pair once
// Context Lens has accepted it. Context Lens keeps its own full copy.
import fs from "node:fs";
import path from "node:path";
import {
  blankRedactedThinking,
  buildCapture,
  classify,
  splitCompleteLines,
} from "./lib.mjs";

const DIR = process.env.BODIES_DIR ?? "/bodies";
const INGEST_URL =
  process.env.INGEST_URL ?? "http://context-lens:4041/api/ingest";
const POLL_MS = Number(process.env.POLL_MS ?? 2000);
// Pairs that could not be ingested, and rotated indexes, are kept this long.
const RETENTION_MS = Number(process.env.RETENTION_DAYS ?? 3) * 86_400_000;
const ROTATE_BYTES = Number(process.env.ROTATE_MB ?? 20) * 1024 * 1024;
// Body files are written before their index line, but give slow mounts time.
const MISSING_GRACE_MS = 60_000;
// After the index is renamed, a writer that already had it open may still append.
const DRAIN_MS = 120_000;
const SWEEP_MS = 10 * 60_000;

const INDEX = path.join(DIR, "index.jsonl");
const STATE = path.join(DIR, ".ingest-state.json");

const log = (...args) => console.log(new Date().toISOString(), ...args);

function loadState() {
  try {
    return JSON.parse(fs.readFileSync(STATE, "utf8"));
  } catch {
    return { offset: 0, rotated: null };
  }
}

function saveState(state) {
  fs.writeFileSync(`${STATE}.tmp`, JSON.stringify(state));
  fs.renameSync(`${STATE}.tmp`, STATE);
}

function sizeOf(file) {
  try {
    return fs.statSync(file).size;
  } catch {
    return null;
  }
}

function removeQuietly(file) {
  try {
    fs.unlinkSync(file);
  } catch {
    /* already gone */
  }
}

/** Returns "done" to move past the line, or "retry" to stop and try it again later. */
async function handle(entry) {
  const requestFile = path.join(DIR, entry.request_file);
  const responseFile = path.join(DIR, entry.response_file);
  let requestText;
  let responseText;
  try {
    requestText = fs.readFileSync(requestFile, "utf8");
    responseText = fs.readFileSync(responseFile, "utf8");
  } catch {
    if (Date.now() - Date.parse(entry.timestamp) < MISSING_GRACE_MS) return "retry";
    log(`skip ${entry.request_id}: body files missing`);
    return "done";
  }

  const request = JSON.parse(requestText);
  const kind = classify(request);
  if (kind !== "ingest") {
    if (kind === "continuation") {
      log(`skip ${entry.request_id}: thread continuation (set CLAUDE_CODE_TETHER_LIVE=0)`);
    }
    removeQuietly(requestFile);
    removeQuietly(responseFile);
    return "done";
  }

  const response = JSON.parse(responseText);
  blankRedactedThinking(request, response);
  const capture = buildCapture(entry, request, response, {
    request: Buffer.byteLength(requestText),
    response: Buffer.byteLength(responseText),
  });

  let res;
  try {
    res = await fetch(INGEST_URL, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(capture),
      signal: AbortSignal.timeout(30_000),
    });
  } catch (err) {
    log(`Context Lens unreachable (${err.message}); will retry`);
    return "retry";
  }
  if (res.ok) {
    removeQuietly(requestFile);
    removeQuietly(responseFile);
    return "done";
  }
  if (res.status >= 500) {
    log(`Context Lens returned ${res.status}; will retry`);
    return "retry";
  }
  // Rejected as invalid: retrying won't help. The sweep removes the files later.
  log(`skip ${entry.request_id}: ingest rejected ${res.status} ${await res.text()}`);
  return "done";
}

/** Process complete lines of `file` from `offset`. Returns the new offset and whether it stalled. */
async function follow(file, offset) {
  const size = sizeOf(file);
  if (size === null || size <= offset) return { offset, stalled: false };
  const buffer = Buffer.alloc(size - offset);
  const fd = fs.openSync(file, "r");
  try {
    fs.readSync(fd, buffer, 0, buffer.length, offset);
  } finally {
    fs.closeSync(fd);
  }
  for (const line of splitCompleteLines(buffer)) {
    if (line.text) {
      let entry;
      try {
        entry = JSON.parse(line.text);
      } catch {
        log(`skip unparseable index line at offset ${offset}`);
      }
      if (entry && (await handle(entry)) === "retry") return { offset, stalled: true };
    }
    offset += line.bytes;
  }
  return { offset, stalled: false };
}

async function tick(state) {
  if (state.rotated) {
    const r = state.rotated;
    const result = await follow(r.file, r.offset);
    r.offset = result.offset;
    if (result.stalled) return true;
    if (Date.now() - r.at > DRAIN_MS && r.offset >= (sizeOf(r.file) ?? 0)) {
      removeQuietly(r.file);
      state.rotated = null;
    }
  }

  const size = sizeOf(INDEX);
  if (size === null) return false;
  if (size < state.offset) state.offset = 0; // replaced or truncated
  const result = await follow(INDEX, state.offset);
  state.offset = result.offset;
  if (result.stalled) return true;

  if (!state.rotated && size >= ROTATE_BYTES && state.offset >= size) {
    const rotatedFile = path.join(DIR, `index-${Date.now()}.jsonl`);
    try {
      fs.renameSync(INDEX, rotatedFile);
      state.rotated = { file: rotatedFile, offset: state.offset, at: Date.now() };
      state.offset = 0;
    } catch (err) {
      // Windows refuses while Claude Code has the file open; try next time.
      log(`index rotation deferred: ${err.message}`);
    }
  }
  return false;
}

function sweep(state) {
  const cutoff = Date.now() - RETENTION_MS;
  let removed = 0;
  for (const name of fs.readdirSync(DIR)) {
    const isBody = /\.(request|response)\.json$/.test(name);
    const isOldIndex = /^index-\d+\.jsonl$/.test(name);
    if (!isBody && !isOldIndex) continue;
    const file = path.join(DIR, name);
    if (state.rotated?.file === file) continue;
    try {
      if (fs.statSync(file).mtimeMs < cutoff) {
        fs.unlinkSync(file);
        removed++;
      }
    } catch {
      /* raced with ingest */
    }
  }
  if (removed > 0) log(`swept ${removed} files older than retention`);
}

async function main() {
  fs.mkdirSync(DIR, { recursive: true });
  const state = loadState();
  log(`following ${INDEX} from offset ${state.offset}, posting to ${INGEST_URL}`);
  let stopping = false;
  for (const signal of ["SIGTERM", "SIGINT"]) {
    process.on(signal, () => {
      stopping = true;
    });
  }

  let backoff = POLL_MS;
  let lastSweep = 0;
  while (!stopping) {
    let stalled = false;
    try {
      stalled = await tick(state);
      saveState(state);
      if (Date.now() - lastSweep > SWEEP_MS) {
        sweep(state);
        lastSweep = Date.now();
      }
    } catch (err) {
      log(`error: ${err.stack ?? err}`);
      stalled = true;
    }
    backoff = stalled ? Math.min(backoff * 2, 60_000) : POLL_MS;
    await new Promise((resolve) => setTimeout(resolve, backoff));
  }
  saveState(state);
}

main();

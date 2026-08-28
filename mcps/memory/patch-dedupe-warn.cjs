#!/usr/bin/env node
/**
 * Build-time patch: warn on probable duplicate entities at create time.
 *
 * Upstream createEntities() dedupes on exact name equality:
 *     entities.filter(e => !graph.entities.some(x => x.name === e.name))
 * That check cannot see the duplicates that actually occur. Two real examples
 * from this store:
 *   - "Context Lens" and "context-lens" both existed (differ only in case and
 *     a separator).
 *   - "opencode-session-history-sharing" and "project_opencode_session_sharing"
 *     both existed, sharing ZERO name tokens but 47% of their observation text.
 * The second is invisible to any name-based check, which is why a content
 * comparison is the load-bearing half of this patch.
 *
 * PURELY ADDITIVE. The dedupe behaviour is deliberately NOT widened. On an
 * exact-name collision upstream drops the incoming entity AND its observations
 * silently -- it does not merge them -- so matching more loosely would lose
 * more data, not less. This patch changes no control flow: it appends an
 * advisory to the tool's text response and lets the write proceed. The agent
 * reads it at the moment it is about to fragment a subject, which is the only
 * moment the fix is cheap.
 *
 * Scoring is Jaccard over observation tokens. Deliberately no embeddings: it
 * needs no model, no network and no dependency, and a threshold-free advisory
 * cannot silently drop a real fact the way a similarity cutoff can.
 *
 * FAILS THE BUILD (exit 1) if either anchor is missing, for the same reason as
 * patch-atomic-write: a silently no-op patch ships an unprotected server that
 * everyone believes is protected.
 */
'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { execSync } = require('node:child_process');

const PKG = '@modelcontextprotocol/server-memory';

// --- anchor 1: the manager method -------------------------------------------
const ANCHOR_CREATE =
  '    async createEntities(entities) {\n' +
  '        const graph = await this.loadGraph();\n' +
  '        const newEntities = entities.filter(e => !graph.entities.some(existingEntity => existingEntity.name === e.name));\n' +
  '        graph.entities.push(...newEntities);\n' +
  '        await this.saveGraph(graph);\n' +
  '        return newEntities;\n' +
  '    }';

const REPLACEMENT_CREATE = [
  '    _dupTokens(observations) {',
  '        const text = (observations || []).join(" ").toLowerCase();',
  '        const words = text.match(/[a-z][a-z0-9_.-]{3,}/g) || [];',
  '        return new Set(words);',
  '    }',
  '    _dupNormName(name) {',
  '        return String(name || "").toLowerCase().replace(/[^a-z0-9]/g, "");',
  '    }',
  '    _dupFindSimilar(entity, existing) {',
  '        const hits = [];',
  '        const normNew = this._dupNormName(entity.name);',
  '        const tokNew = this._dupTokens(entity.observations);',
  '        for (const other of existing) {',
  '            if (other.name === entity.name) continue;',
  '            if (this._dupNormName(other.name) === normNew) {',
  '                hits.push({ name: other.name, why: "same name ignoring case and separators" });',
  '                continue;',
  '            }',
  '            if (tokNew.size < 8) continue;',
  '            const tokOther = this._dupTokens(other.observations);',
  '            if (tokOther.size < 8) continue;',
  '            let shared = 0;',
  '            for (const t of tokNew) if (tokOther.has(t)) shared++;',
  '            const union = tokNew.size + tokOther.size - shared;',
  '            const score = union > 0 ? shared / union : 0;',
  '            if (score >= 0.35) {',
  '                hits.push({ name: other.name, why: "shares " + Math.round(score * 100) + "% of observation wording" });',
  '            }',
  '        }',
  '        return hits;',
  '    }',
  '    async createEntities(entities) {',
  '        const graph = await this.loadGraph();',
  '        const newEntities = entities.filter(e => !graph.entities.some(existingEntity => existingEntity.name === e.name));',
  '        this._dupWarnings = [];',
  '        for (const e of newEntities) {',
  '            const hits = this._dupFindSimilar(e, graph.entities);',
  '            if (hits.length) {',
  '                this._dupWarnings.push({ created: e.name, resembles: hits });',
  '            }',
  '        }',
  '        const skipped = entities.filter(e => !newEntities.includes(e));',
  '        for (const e of skipped) {',
  '            this._dupWarnings.push({',
  '                created: null,',
  '                notCreated: e.name,',
  '                resembles: [{ name: e.name, why: "an entity with this exact name already exists; this create was a SILENT NO-OP and its observations were NOT added. Use add_observations instead." }]',
  '            });',
  '        }',
  '        graph.entities.push(...newEntities);',
  '        await this.saveGraph(graph);',
  '        return newEntities;',
  '    }',
].join('\n');

// --- anchor 2: the tool handler, where the text response is built -----------
const ANCHOR_TOOL =
  '    const result = await knowledgeGraphManager.createEntities(entities);\n' +
  '    notifyGraphUpdated();\n' +
  '    return {\n' +
  '        content: [{ type: "text", text: JSON.stringify(result, null, 2) }],\n' +
  '        structuredContent: { entities: result }\n' +
  '    };';

const REPLACEMENT_TOOL = [
  '    const result = await knowledgeGraphManager.createEntities(entities);',
  '    notifyGraphUpdated();',
  '    let _dupNote = "";',
  '    const _w = knowledgeGraphManager._dupWarnings || [];',
  '    if (_w.length) {',
  '        _dupNote = "\\n\\nPOSSIBLE DUPLICATES -- this graph\'s dominant defect is one subject split across several entities. Check before continuing; prefer add_observations on the existing entity over a new sibling.\\n"',
  '            + _w.map(w => w.created',
  '                ? "  created \\"" + w.created + "\\" but it resembles: " + w.resembles.map(h => "\\"" + h.name + "\\" (" + h.why + ")").join(", ")',
  '                : "  NOT created: \\"" + w.notCreated + "\\" -- " + w.resembles[0].why).join("\\n");',
  '    }',
  '    return {',
  '        content: [{ type: "text", text: JSON.stringify(result, null, 2) + _dupNote }],',
  '        structuredContent: { entities: result }',
  '    };',
].join('\n');

const PATCH_MARKER = '_dupFindSimilar';

function fail(msg) {
  console.error('');
  console.error('  PATCH FAILED: ' + msg);
  console.error('  Refusing to build an image whose duplicate check is known-broken and silent.');
  console.error('');
  process.exit(1);
}

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
  console.log('  patch-dedupe-warn: already patched, nothing to do -> ' + target);
  process.exit(0);
}

for (const [label, anchor] of [['createEntities', ANCHOR_CREATE], ['create_entities tool handler', ANCHOR_TOOL]]) {
  const n = original.split(anchor).length - 1;
  if (n !== 1) {
    fail(
      'expected exactly 1 occurrence of the ' + label + ' anchor in ' + target +
      ', found ' + n + '. Upstream likely refactored it; re-derive the anchor before building.'
    );
  }
}

let patched = original.replace(ANCHOR_CREATE, REPLACEMENT_CREATE).replace(ANCHOR_TOOL, REPLACEMENT_TOOL);

if (patched === original) {
  fail('post-replacement verification failed: file content unchanged.');
}
if (!patched.includes(PATCH_MARKER) || !patched.includes('POSSIBLE DUPLICATES')) {
  fail('post-replacement verification failed: expected markers absent.');
}

fs.writeFileSync(target, patched, 'utf8');

const readback = fs.readFileSync(target, 'utf8');
if (!readback.includes(PATCH_MARKER) || !readback.includes('POSSIBLE DUPLICATES')) {
  fail('readback verification failed: patch did not persist to ' + target);
}

console.log('  patch-dedupe-warn: create_entities now reports probable duplicates -> ' + target);

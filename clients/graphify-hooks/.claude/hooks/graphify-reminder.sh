#!/usr/bin/env bash
set -euo pipefail

case "${1:-}" in
  search|read) mode=$1 ;;
  *) printf 'graphify-reminder: expected search or read\n' >&2; exit 1 ;;
esac

[ -f graphify-out/graph.json ] || exit 0

# Windows can expose a python3 Store alias even when Python is installed.
if command -v python >/dev/null 2>&1 &&
   python -c 'import sys; sys.exit(sys.version_info.major != 3)' >/dev/null 2>&1; then
  interpreter=python
elif command -v python3 >/dev/null 2>&1 &&
     python3 -c 'import sys; sys.exit(sys.version_info.major != 3)' >/dev/null 2>&1; then
  interpreter=python3
else
  printf 'graphify-reminder: a working Python 3 interpreter is required\n' >&2
  exit 1
fi

case "$mode" in
  search)
    CMD=$("$interpreter" -c "import json,sys; d=json.load(sys.stdin); print(d.get('tool_input',d).get('command',''))")
    case "$CMD" in
      *grep*|*rg\ *|*ripgrep*|*find\ *|*fd\ *|*ack\ *|*ag\ *)
        printf '%s\n' '{"hookSpecificOutput":{"hookEventName":"PreToolUse","additionalContext":"MANDATORY: graphify-out/graph.json exists. You MUST run `graphify query \"<question>\"` before grepping raw files. Only grep after graphify has oriented you, or to modify/debug specific lines."}}'
        ;;
    esac
    ;;
  read)
    HIT=$("$interpreter" -c "import json,sys;d=json.load(sys.stdin);t=d.get('tool_input',d);exts=('.py','.js','.ts','.tsx','.jsx','.astro','.vue','.svelte','.go','.rs','.java','.rb','.c','.h','.cpp','.hpp','.cc','.cs','.kt','.swift','.php','.scala','.lua','.sh','.md','.rst','.txt','.mdx');vals=[str(t.get('file_path') or ''),str(t.get('pattern') or ''),str(t.get('path') or '')];j=' '.join(vals).lower().replace(chr(92),'/');tails=[('.'+x.rsplit('.',1)[-1]) for v in vals if v for x in [v.lower().replace(chr(92),'/').rsplit('/',1)[-1]] if '.' in x];sys.stdout.write('1' if 'graphify-out/' not in j and any(tl in exts for tl in tails) else '')")
    if [ "$HIT" = 1 ]; then
      printf '%s\n' '{"hookSpecificOutput":{"hookEventName":"PreToolUse","additionalContext":"MANDATORY: graphify-out/graph.json exists. You MUST run graphify before reading source files. Use: `graphify query \"<question>\"` (scoped subgraph), `graphify explain \"<concept>\"`, or `graphify path \"<A>\" \"<B>\"`. Only read raw files after graphify has oriented you, or to modify/debug specific lines. This rule applies to subagents too \u2014 include it in every subagent prompt involving code exploration."}}'
    fi
    ;;
esac

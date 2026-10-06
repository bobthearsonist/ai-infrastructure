# Graphify reminders

`graphify-reminder.sh` supplies the existing search and source-read reminders to
Claude Code and Copilot CLI. Both use the same Bash script; the Windows
`powershell` hook entry launches Bash explicitly and propagates its exit code.

Bash must be on `PATH` (Git Bash, not the WSL launcher, on Windows). The script
selects a working Python 3 interpreter from `python` or `python3`, avoiding
Windows Store aliases that exist on `PATH` but cannot execute.

## Deploy

The canonical source is `ai-infrastructure/clients/graphify-hooks/.claude`.
Copy `hooks/graphify-reminder.sh`, this README, and
`tests/validate_graphify_hooks.py` into the corresponding `.claude` directories
in the target workspace. Merge the two `PreToolUse` entries from the bundle's
`settings.json` into the workspace's `.claude/settings.json`, replacing the old
inline graphify reminders while preserving unrelated hooks and settings. For a
workspace with no existing settings, the bundle's settings file can be copied
directly.

Do not run `graphify claude install` over this configuration without reviewing
the generated settings; an installer may replace the hook entries. Reload both
clients after deploying. These are workspace hooks, not plugin hooks: no plugin
release, marketplace sync, or user-level Claude configuration change is needed.

## Regression tests

Run the deterministic regression suite from the target workspace root:

```powershell
python .claude\tests\validate_graphify_hooks.py
```

Or validate the canonical bundle from the infrastructure repository root:

```powershell
python clients\graphify-hooks\.claude\tests\validate_graphify_hooks.py
```

On macOS or Linux, use `python3` and the corresponding POSIX path.

The suite runs the configured commands in isolated fixtures, checks exact
reminder JSON and stdin handling, exercises matching/nonmatching inputs and
missing graphs, and checks error exit codes and interpreter fallback. It also
tests each PowerShell version available on `PATH`. No AI calls or configuration
changes are made.

For client integration testing, enable hooks in a disposable project, copy this
`.claude` configuration and script there, and create a placeholder
`graphify-out/graph.json`. A search command and a source-file read should each
produce the corresponding reminder. Without the graph file, neither should
produce output. Reload the client after changing hook definitions.

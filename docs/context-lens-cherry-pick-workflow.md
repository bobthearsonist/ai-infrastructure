# Context Lens: Cherry-Pick Staged Changes Workflow

## Purpose

Maintain a local `main` branch that has **all in-flight fixes applied** while each fix lives on its own branch as a separate PR to upstream. This lets you use a fully-patched local build day-to-day while shepherding individual PRs through upstream review.

## Architecture

```
upstream/main ← PRs from your fork branches
    ↑
origin/main (your fork, tracks upstream)
    ↑
local main (staged cherry-picks from all active branches)
    ↑
┌───┴───┬──────────┬──────────┐
fix/a   fix/b   feat/c   fix/d    ← worktree branches, each = 1 PR
```

**Key invariant**: Local `main` is never committed ahead of `origin/main`. All local-only changes live as **staged but uncommitted** cherry-picks.

## Setup

### Remotes

```bash
git remote add upstream https://github.com/larsderidder/context-lens.git
git remote add origin https://github.com/bobthearsonist/context-lens.git  # your fork
```

### Worktrees

Each fix/feature gets its own worktree branched from `origin/main`:

```bash
# From the main clone directory
git worktree add ../context-lens-fix-foo fix/foo
```

## Daily Workflow

### 1. Develop on worktree branches

Work in each worktree independently. Make conventional commits. Each branch = one PR.

```bash
cd ../context-lens-fix-foo
# ... make changes, commit ...
git push origin fix/foo
# Open PR against upstream/main
```

### 2. Stack changes on local main

After committing on a branch, cherry-pick onto main **without committing**:

```bash
cd ../context-lens   # main clone
git checkout main

# Cherry-pick each branch's commits without committing
# For a single commit:
git cherry-pick --no-commit <commit-sha>

# For a branch with multiple commits:
git cherry-pick --no-commit origin/main..<branch-name>
```

This stages the changes but does not create a commit. Repeat for each active branch. All fixes are now applied to your working tree.

### 3. Use your fully-patched main

Run context-lens from this directory. All fixes are live. The staged changes are uncommitted so `origin/main` stays clean.

## Syncing with Upstream

Chain: `upstream/main` → `origin/main` → feature branches. Never rebase branches directly on upstream — always go through your fork's main.

```bash
# 1. Stash your staged cherry-picks
git stash push -m "staged cherry-picks"

# 2. Sync main: upstream → local → fork
git checkout main
git fetch --all
git rebase upstream/main
git push origin main              # may need --force-with-lease if main was rebased

# 3. Rebase active branches onto synced main
git rebase main fix/still-open-a
git rebase main fix/still-open-b
# Branches whose commits were merged upstream will get skipped automatically
git push --force-with-lease origin fix/still-open-a fix/still-open-b

# 4. Switch back to main and rebuild staged state (only branches with real diffs)
git checkout main
git cherry-pick --no-commit origin/main..fix/still-open-a
git cherry-pick --no-commit origin/main..fix/still-open-b

# 5. Clean up the stash (don't pop — rebuild is cleaner)
git stash drop
```

**Why rebuild instead of popping the stash?** The stash may contain changes from now-merged PRs. Rebuilding from only the remaining open branches avoids conflicts and keeps the staged state clean.

**Why rebase branches too?** If you only rebuild the cherry-picks without rebasing, the branch diffs balloon with upstream noise. Rebasing keeps each branch's diff minimal and PRs clean.

## Switching Machines

To recreate the staged state on another machine:

```bash
# 1. Clone your fork
git clone https://github.com/bobthearsonist/context-lens.git
cd context-lens
git remote add upstream https://github.com/larsderidder/context-lens.git

# 2. Ensure main is up to date
git fetch --all
git rebase upstream/main
git push origin main

# 3. Cherry-pick from each open PR branch (without committing)
git cherry-pick --no-commit origin/main..origin/fix/branch-a
git cherry-pick --no-commit origin/main..origin/fix/branch-b
# ... repeat for each active branch

# 4. Optionally recreate worktrees for branches you're still developing
git worktree add ../context-lens-fix-branch-a fix/branch-a
```

### Mac Resume — April 2026

Active branches (all rebased onto upstream/main at v0.8.0+):

| Branch | Files | What |
|--------|-------|------|
| `fix/today-cost-scope` | 7 (gitattributes, API, UI) | Scope KPI cost/requests to date range |
| `feat/session-linking-agent-relationships` | 5 (design docs) | Session linking design spec + diagrams |
| `copilot/fix-session-eviction-data-loss` | 2 (store.ts + test) | Archive sessions before eviction |

**Merged/absorbed** (can be cleaned up):
- `fix/claude-session-header` — merged upstream as PR #47
- `feat/show-session-label`, `fix/claude-working-dir` — stale, no unique work

```bash
# Clone (or cd into existing clone) and fetch
git clone https://github.com/bobthearsonist/context-lens.git
cd context-lens
git remote add upstream https://github.com/larsderidder/context-lens.git
git fetch --all

# Sync main with upstream
git checkout main
git rebase upstream/main

# Stack all 3 active branches as staged changes
git cherry-pick --no-commit origin/main..origin/fix/today-cost-scope
git cherry-pick --no-commit origin/main..origin/feat/session-linking-agent-relationships
git cherry-pick --no-commit origin/main..origin/copilot/fix-session-eviction-data-loss

# Verify staged state (should show ~14 files, ~497 insertions)
git diff --cached --stat

# Recreate worktrees for active development
git worktree add ../context-lens-today-cost-scope origin/fix/today-cost-scope
git worktree add ../context-lens-session-linking origin/feat/session-linking-agent-relationships
git worktree add ../context-lens-eviction-fix origin/copilot/fix-session-eviction-data-loss
```

## Branch Lifecycle

| State | Action |
|-------|--------|
| New fix needed | Create worktree branch from `origin/main` |
| Fix ready for review | Push to fork, open PR to upstream |
| PR merged upstream | Drop from cherry-pick list, sync main |
| PR rejected/abandoned | Delete branch, remove from cherry-pick list, rebuild staged state |

## Tips

- **List active branches**: `git branch --no-merged origin/main` shows what still needs cherry-picking
- **Check staged state**: `git diff --cached --stat` shows your current cherry-pick stack
- **Abort and rebuild**: If staged state gets messy, `git restore --staged .` then re-cherry-pick
- **Conflict during cherry-pick**: Resolve manually, then `git add` the resolved files (don't commit)

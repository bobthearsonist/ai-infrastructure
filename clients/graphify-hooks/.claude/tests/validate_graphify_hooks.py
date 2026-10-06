import base64
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


SETTINGS = Path(__file__).resolve().parents[1] / "settings.json"
BASH = shutil.which("bash")
if BASH is None:
    raise SystemExit("Bash is required to validate the graphify hooks.")
SHELLS = [("Bash (Claude command)", BASH)]
for name, executable in (("PowerShell 7", "pwsh"), ("PowerShell 5.1", "powershell")):
    resolved = shutil.which(executable)
    if resolved:
        SHELLS.append((name, resolved))
CASES = [
    ("search-hit", "Bash", {"command": "rg needle source.py"}, True, True),
    ("search-miss", "Bash", {"command": "echo hello"}, True, False),
    ("search-no-graph", "Bash", {"command": "rg needle source.py"}, False, False),
    ("read-hit", "Read|Glob", {"file_path": r"C:\repo\source.py"}, True, True),
    ("glob-hit", "Read|Glob", {"pattern": "**/*.ts"}, True, True),
    ("read-graph", "Read|Glob", {"file_path": "graphify-out/report.md"}, True, False),
    ("read-image", "Read|Glob", {"file_path": "logo.png"}, True, False),
    ("read-no-graph", "Read|Glob", {"file_path": "source.py"}, False, False),
    ("unicode-path", "Read|Glob", {"file_path": "src/caf\u00e9.py"}, True, True),
]
SEARCH_CONTEXT = 'MANDATORY: graphify-out/graph.json exists. You MUST run `graphify query "<question>"` before grepping raw files. Only grep after graphify has oriented you, or to modify/debug specific lines.'
READ_CONTEXT = 'MANDATORY: graphify-out/graph.json exists. You MUST run graphify before reading source files. Use: `graphify query "<question>"` (scoped subgraph), `graphify explain "<concept>"`, or `graphify path "<A>" "<B>"`. Only read raw files after graphify has oriented you, or to modify/debug specific lines. This rule applies to subagents too \u2014 include it in every subagent prompt involving code exploration.'


def run(shell, command, cwd, payload, env=None):
    if Path(shell).name.lower() in ("bash", "bash.exe"):
        arguments = [shell, "-c", command]
    else:
        encoded = base64.b64encode(command.encode("utf-16-le")).decode("ascii")
        arguments = [shell, "-NoLogo", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded]
    return subprocess.run(
        arguments,
        cwd=cwd,
        input=payload if isinstance(payload, str) else json.dumps(payload),
        text=True,
        encoding="utf-8",
        capture_output=True,
        timeout=15,
        env=env,
    )


hooks = {
    entry["matcher"]: entry["hooks"][0]
    for entry in json.loads(SETTINGS.read_text(encoding="utf-8"))["hooks"]["PreToolUse"]
}
failures = []
checks = 0
with tempfile.TemporaryDirectory(prefix="graphify-hook-test-") as temp:
    root = Path(temp)
    graph_root = root / "with-graph"
    plain_root = root / "without-graph"
    (graph_root / "graphify-out").mkdir(parents=True)
    (graph_root / "graphify-out" / "graph.json").write_text("{}", encoding="utf-8")
    plain_root.mkdir()
    for cwd in (graph_root, plain_root):
        (cwd / ".claude" / "hooks").mkdir(parents=True)
        shutil.copy2(
            SETTINGS.parent / "hooks" / "graphify-reminder.sh",
            cwd / ".claude" / "hooks" / "graphify-reminder.sh",
        )
    for shell_name, shell in SHELLS:
        for name, matcher, args, graph, expected in CASES:
            checks += 1
            payload = {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash" if matcher == "Bash" else "Read",
                "tool_input": args,
            }
            result = run(
                shell, hooks[matcher]["command" if shell_name.startswith("Bash") else "powershell"],
                graph_root if graph else plain_root, payload,
            )
            reason = None
            output = result.stdout.strip()
            if result.returncode != 0:
                reason = f"exit {result.returncode}: {result.stderr.strip()[:240]}"
            elif expected:
                try:
                    parsed = json.loads(output)
                    context = parsed["hookSpecificOutput"]["additionalContext"]
                    expected_context = SEARCH_CONTEXT if matcher == "Bash" else READ_CONTEXT
                    if context != expected_context or parsed["hookSpecificOutput"]["hookEventName"] != "PreToolUse":
                        reason = f"unexpected context: {context!r}"
                except (ValueError, KeyError) as error:
                    reason = f"missing/invalid reminder output: {output!r} ({error})"
            elif output:
                reason = f"unexpected output: {output!r}"
            if reason:
                failures.append((shell_name, name, reason))
                print(f"FAIL {shell_name} {name}: {reason}")
            else:
                print(f"PASS {shell_name} {name}")
        for name, command, payload in (
            ("malformed-input", hooks["Bash"]["command" if shell_name.startswith("Bash") else "powershell"], "{bad-json"),
            ("invalid-mode", hooks["Bash"]["command" if shell_name.startswith("Bash") else "powershell"].replace(" search", " invalid"), {}),
        ):
            checks += 1
            result = run(shell, command, graph_root, payload)
            if result.returncode == 0 or not result.stderr.strip() or result.stdout.strip():
                failures.append((shell_name, name, "error must be visible and non-zero"))
                print(f"FAIL {shell_name} {name}: exit={result.returncode}, stderr={result.stderr!r}")
            else:
                print(f"PASS {shell_name} {name}")

    bin_dir = root / "bin"
    bin_dir.mkdir()
    python_stub = bin_dir / "python"
    python_stub.write_text("#!/bin/bash\nexit 1\n", encoding="utf-8")
    python_stub.chmod(0o755)
    python3_shim = bin_dir / "python3"
    python_path = sys.executable.replace("\\", "/").replace("'", "'\\''")
    python3_shim.write_text(f"#!/bin/bash\nexec '{python_path}' \"$@\"\n", encoding="utf-8")
    python3_shim.chmod(0o755)
    env = os.environ.copy()
    env["PATH"] = str(bin_dir) + os.pathsep + str(Path(BASH).parent)
    for name, missing in (("python3-fallback", False), ("missing-python", True)):
        if missing:
            python3_shim.write_text("#!/bin/bash\nexit 1\n", encoding="utf-8")
        checks += 1
        result = run(BASH, hooks["Bash"]["command"], graph_root,
                     {"tool_input": {"command": "grep needle source.py"}}, env)
        if missing:
            passed = result.returncode != 0 and "Python 3 interpreter is required" in result.stderr
        else:
            passed = result.returncode == 0 and "before grepping raw files" in result.stdout
        if passed:
            print(f"PASS {name}")
        else:
            failures.append(("Bash", name, result.stderr))
            print(f"FAIL {name}: exit={result.returncode}, stdout={result.stdout!r}, stderr={result.stderr!r}")
print(f"{checks - len(failures)}/{checks} passed")
raise SystemExit(bool(failures))

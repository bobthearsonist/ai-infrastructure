# Amazon Orders MCP

[`alexdlaird/amazon-orders-mcp`](https://github.com/alexdlaird/amazon-orders-mcp) — Amazon order
history, tracking, invoices and transactions, by the author of the `amazon-orders` library it wraps.

Runs as a **launchd LaunchAgent host bridge**, not a container. See
[../fantastical/readme.md](../fantastical/readme.md) for the Rosetta table mapping `manage.sh`
verbs onto `docker compose` ones — this service follows the same pattern.

| | |
|---|---|
| Port | 7014 (SSE) |
| Gateway URL | `http://host.docker.internal:7014/sse` |
| mcpx tool group | `personal-finance` (alongside `monarch-money`) |
| Label | `com.bobthearsonist.amazon-orders-mcp` |
| Logs | `~/Library/Logs/amazon-orders-mcp.{out,err}.log` |
| Session jar | `~/.config/amazonorders/cookies.json` |

## Why a host bridge and not a container

`amazon-orders` has no official API — it authenticates by replaying a browser session, which
`amazon-orders login --browser` establishes on Amazon's own sign-in page and persists to
`~/.config/amazonorders/cookies.json`.

1. **The sign-in needs a GUI session.** A LaunchDaemon and a Docker container both lack one.
   Containerising this would mean adopting a headless/remote sign-in flow for no gain.
2. **The credential at rest is a live Amazon session** — order history, addresses,
   payment-method tails. On the host it stays in the user's home directory. In a container it
   would have to be bind-mounted into the gateway that *every* MCP consumer shares.

This is placement option (3) of three for a stdio MCP here; the other two are a `stdio-proxy`
child (`../stdio-proxy/servers.home.json`) and a standalone bridged container
(`../monarch-money/`). Choose the host bridge when the server needs the logged-in GUI session, or
when its credential should not live inside the shared gateway container.

A side benefit: `mcp.json` and `app.yaml` are bind-mounted, so adding a backend this way needs
**no `docker-compose.yml` edit** at all.

## Sign-in

Interactive, occasional, and the user's own action — neither this bridge nor the MCP server ever
sees the password or the OTP:

```bash
./manage.sh login
```

The `--browser` flag needs the `browser` extra, which plain `uvx amazon-orders` does **not** pull
in; `manage.sh` therefore invokes `uvx --from 'amazon-orders[browser]'`. Without `--from` it exits
complaining about a missing extra rather than opening anything.

`./manage.sh jar` reports whether the jar exists, and its age, without printing its contents.

Restart the bridge after a first sign-in (`./manage.sh restart`) — `--minConcurrency 1` pre-warms a
child at boot, and that child started before the jar existed.

## Verifying

```bash
./manage.sh test
```

Probes the MCP handshake, **not** `/healthz`. In supergateway 3.3.0 the health endpoint is an
unconditional `res.send('ok')` with no reference to the child process or the pool, so it reports
healthy on a completely dead bridge — it did exactly that on the Fantastical bridge for 12 days.

Through the gateway, from a client that mcpx identifies as an allowed consumer:

```bash
docker restart mcpx
```

Note that mcpx's own `tools/list` names tools `<service>__<tool>` (e.g. `amazon-orders__find_charge`);
the `mcp__mcpx__<service>__<tool>` form is composed client-side. A raw JSON-RPC probe that does not
present a recognised `clientInfo.name` falls back to the `default` permission group, which excludes
`personal-finance` — so "no amazon-orders tools" from such a probe means *unidentified consumer*,
not *broken deployment*.

## When the session expires

```bash
./manage.sh reauth
```

Runs the whole recovery in the only order that works, probing between steps:
re-login → verify the jar actually changed → ask the running bridge whether it
can see a session → restart the bridge only if it cannot → offer to bounce the
gateway, which the bridge restart makes necessary.

The pieces are also available separately:

| Command | Does |
|---|---|
| `./manage.sh probe` | asks the running bridge on :7014 whether it sees a valid session (exit 0 = yes, 1 = no) |
| `./manage.sh bounce-gateway` | `docker stop -t 30 mcpx` + `docker start mcpx`, then waits for :9000 |

### Diagnosing

`check_session` returns `signed_in: false` for *both* "never signed in" and
"expired", so it cannot tell them apart. `./manage.sh jar` can — it reports the
jar's presence, mtime and size without printing its contents:

- **absent** → never signed in; `login` is the fix
- **present** → signed in at some point, so a `signed_in: false` means the
  session was rejected, i.e. expired or revoked

Note the mtime is *not* a session age: the child rewrites the jar as it works
(see below), so mtime tracks last use. A recently-touched jar can still hold a
session Amazon has stopped accepting.

### Why a re-login forces a gateway bounce

Measured 2026-11-23: a running MCP child holds its Amazon session **in memory**,
not re-read from the jar per call — deleting the jar outright left the same child
still reporting `signed_in: true`. So a freshly written jar cannot be assumed to
reach an already-running child, which is why `reauth` restarts the bridge.

That restart then orphans mcpx's long-lived upstream SSE session; mcpx does not
re-dial, and every tool call fails with `MCP error -32602: Invalid request
parameters` while `./manage.sh test` reports the bridge perfectly healthy. The
parameters are fine — the session is dead. Only bouncing mcpx clears it, which
briefly drops *every* mcpx-served MCP. `reauth` therefore prompts before doing
it, and skips it entirely when the probe shows nothing was broken.

The child also **writes refreshed cookies back** to the jar as it works (observed
growing 4165 → 4399 bytes across a few calls), so the jar's mtime tracks last
use, not last login.

## Deliberate omissions

- **No version pin** on `amazon-orders-mcp`. Upstream's README warns that older versions break as
  Amazon changes its markup, and the 6.0.0 changelog shows WAF challenge solvers and encrypted
  order cards landing through 2026. `uvx` re-resolves to latest and caches. Contrast the `mcp<2`
  pin on `photoshop` in `../stdio-proxy/servers.home.json`, which freezes a library API that
  genuinely stopped moving — the opposite situation.
- **`sign_in` and `update_config` are not in the gateway allowlist.** `sign_in` would let any
  consumer trigger a browser auth flow; `update_config` mutates config. Both remain available
  locally via the CLI. This mirrors the explicit read-only allowlist discipline on
  `monarch-money`, adopted after a `"*"` there once exposed `delete_account`.
- **The `capsolver` / `anticaptcha` / `2captcha` extras are not wired.** The package offers them;
  this deployment does not use them.

## Known caveats

- Amazon has no official orders API, and this is a scraper. Treat it as best-effort and expect
  breakage after Amazon markup changes; the fix is usually just a newer release, which the
  unpinned `uvx` invocation picks up on the next child spawn.
- `HOME` is load-bearing in the plist. `amazon-orders` resolves its config dir from
  `expanduser("~")`; with `HOME` unset or wrong under launchd the server starts cleanly and reports
  `signed_in: false` forever, because it is looking for the jar in the wrong place.
- `docker restart mcpx` has been observed to leave the gateway in a crash loop — its entrypoint
  waits on an inner Docker-in-Docker daemon and fails with `containerd is still running pid=58` /
  `failed to save daemon pid to disk`, because `restart` does not tear down the container's PID
  namespace. Recover with a full `docker stop -t 30 mcpx` then `docker start mcpx`. Unrelated to
  this service, but it will bite anyone following the "restart mcpx after editing app.yaml" step.

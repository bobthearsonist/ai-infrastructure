// Pure helpers for the OTEL raw-body importer, kept free of I/O so they can be tested.

const NEWLINE = 0x0a;

/** Claude Code logs thinking text as this placeholder; the API itself returns "". */
const REDACTED_THINKING = "<REDACTED>";

/**
 * What to do with one logged request:
 * - "continuation": a server-side thread delta that only carries the newest
 *   messages. Context Lens would chart it as the whole context, so it is
 *   dropped. Claude Code stops sending these when CLAUDE_CODE_TETHER_LIVE=0.
 * - "quota": Claude Code's one-message usage probe, which would otherwise show
 *   up as a new single-request conversation every time it runs.
 * - "ingest": everything else.
 */
export function classify(request) {
  if (request?.thread?.type === "continue") return "continuation";
  if (isQuotaProbe(request)) return "quota";
  return "ingest";
}

function isQuotaProbe(request) {
  const messages = request?.messages;
  if (!Array.isArray(messages) || messages.length !== 1) return false;
  if (Array.isArray(request.tools) && request.tools.length > 0) return false;
  const content = messages[0]?.content;
  const text =
    typeof content === "string"
      ? content
      : Array.isArray(content) && content.length === 1
        ? content[0]?.text
        : undefined;
  return text === "quota";
}

/** Replace the logger's thinking placeholder with what the API actually sent. */
export function blankRedactedThinking(request, response) {
  const blank = (blocks) => {
    if (!Array.isArray(blocks)) return;
    for (const b of blocks) {
      if (b?.type === "thinking" && b.thinking === REDACTED_THINKING) b.thinking = "";
    }
  };
  for (const m of request?.messages ?? []) blank(m?.content);
  blank(response?.content);
}

/**
 * Shape one logged request/response pair like a capture from the :4040 proxy.
 * The session header lets Context Lens key the conversation as
 * claude_<session id>, exactly as it does for proxied traffic.
 */
export function buildCapture(entry, request, response, sizes) {
  return {
    timestamp: entry.timestamp,
    method: "POST",
    path: "/v1/messages",
    source: "claude",
    provider: "anthropic",
    apiFormat: "anthropic-messages",
    targetUrl: "https://api.anthropic.com/v1/messages",
    requestHeaders: { "x-claude-code-session-id": entry.session_id },
    requestBody: request,
    requestBytes: sizes.request,
    responseStatus: 200,
    responseBody: JSON.stringify(response),
    responseIsStreaming: false,
    responseBytes: sizes.response,
  };
}

/**
 * Split the complete lines off the front of `buffer`. A trailing line without
 * its newline is still being written, so it is left for the next read.
 * Each line comes with its byte length (newline included) so callers can
 * advance a file offset exactly.
 */
export function splitCompleteLines(buffer) {
  const lines = [];
  let start = 0;
  let nl = buffer.indexOf(NEWLINE, start);
  while (nl !== -1) {
    const text = buffer.toString("utf8", start, nl).trim();
    lines.push({ text, bytes: nl + 1 - start });
    start = nl + 1;
    nl = buffer.indexOf(NEWLINE, start);
  }
  return lines;
}

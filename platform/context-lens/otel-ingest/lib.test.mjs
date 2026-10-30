import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  blankRedactedThinking,
  buildCapture,
  classify,
  splitCompleteLines,
} from "./lib.mjs";

describe("classify", () => {
  it("drops thread continuations, which carry only the newest messages", () => {
    const request = {
      thread: { type: "continue", previous_message_id: "msg_1" },
      messages: [{ role: "user", content: "hi" }],
    };
    assert.equal(classify(request), "continuation");
  });

  it("drops Claude Code's quota probe", () => {
    assert.equal(classify({ messages: [{ role: "user", content: "quota" }] }), "quota");
    assert.equal(
      classify({ messages: [{ role: "user", content: [{ type: "text", text: "quota" }] }] }),
      "quota",
    );
  });

  it("ingests a one-word request that is not the probe", () => {
    const withTools = { tools: [{ name: "Read" }], messages: [{ role: "user", content: "quota" }] };
    assert.equal(classify(withTools), "ingest");
    assert.equal(classify({ messages: [{ role: "user", content: "hello" }] }), "ingest");
    assert.equal(classify({ thread: { type: "create" }, messages: [] }), "ingest");
  });
});

describe("blankRedactedThinking", () => {
  it("replaces the logger's placeholder in history and in the response", () => {
    const request = {
      messages: [
        { role: "assistant", content: [{ type: "thinking", thinking: "<REDACTED>", signature: "s" }] },
        { role: "user", content: "plain" },
      ],
    };
    const response = { content: [{ type: "thinking", thinking: "<REDACTED>" }, { type: "text", text: "<REDACTED>" }] };

    blankRedactedThinking(request, response);

    assert.equal(request.messages[0].content[0].thinking, "");
    assert.equal(response.content[0].thinking, "");
    assert.equal(response.content[1].text, "<REDACTED>", "only thinking blocks change");
  });
});

describe("buildCapture", () => {
  it("shapes a pair like a proxy capture keyed by the Claude session", () => {
    const capture = buildCapture(
      { timestamp: "2026-10-30T15:00:00Z", session_id: "abc" },
      { model: "claude-opus-5-5", messages: [] },
      { content: [], usage: { input_tokens: 1 } },
      { request: 10, response: 20 },
    );
    assert.equal(capture.requestHeaders["x-claude-code-session-id"], "abc");
    assert.equal(capture.responseIsStreaming, false);
    assert.deepEqual(JSON.parse(capture.responseBody).usage, { input_tokens: 1 });
    assert.equal(capture.requestBytes, 10);
  });
});

describe("splitCompleteLines", () => {
  it("returns complete lines with byte lengths and leaves a partial line", () => {
    const lines = splitCompleteLines(Buffer.from('{"a":"é"}\n\n{"b":2}\n{"c":'));
    assert.deepEqual(
      lines.map((l) => l.text),
      ['{"a":"é"}', "", '{"b":2}'],
    );
    assert.equal(
      lines.reduce((n, l) => n + l.bytes, 0),
      Buffer.byteLength('{"a":"é"}\n\n{"b":2}\n'),
    );
  });
});

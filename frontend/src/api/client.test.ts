import { describe, expect, it } from "vitest";
import { normalizeGraphEvent, parseSseFrame } from "./client";

describe("SSE frame parser", () => {
  it("parses named events, ids, retry hints and multiline data", () => {
    const frame = [
      "id: event-12",
      "event: graph_event",
      "retry: 2500",
      "data: {\"sequence\":12,",
      "data: \"type\":\"agent_started\"}",
    ].join("\n");
    expect(parseSseFrame(frame)).toEqual({
      id: "event-12",
      event: "graph_event",
      retry: 2500,
      data: "{\"sequence\":12,\n\"type\":\"agent_started\"}",
    });
  });

  it("ignores keepalive comments", () => {
    expect(parseSseFrame(": keepalive")).toBeNull();
  });

  it("normalizes legacy envelopes without UI hints", () => {
    const event = normalizeGraphEvent({
      schema_version: 1,
      event_id: "event-1",
      run_id: "run-1",
      sequence: 1,
      timestamp: "2026-08-17T00:00:00Z",
      type: "run_started",
      stage: "search",
      actor_kind: "workflow",
      actor_id: "orchestrator",
    });
    expect(event.schema_version).toBe(1);
    expect(event.payload).toEqual({});
    expect(event.ui).toMatchObject({ template_key: "event.generic", severity: "info" });
    expect(event.visibility).toBe("user");
  });
});

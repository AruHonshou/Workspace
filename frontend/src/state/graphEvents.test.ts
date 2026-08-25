import { describe, expect, it } from "vitest";
import { DEMO_EVENTS } from "../data/demo";
import { reduceGraphEvents } from "./graphEvents";

describe("GraphEvent projection", () => {
  it("derives fan-out workers without treating them as visible agents", () => {
    const state = reduceGraphEvents(DEMO_EVENTS.slice(0, 13));
    expect(Object.keys(state.agents)).toHaveLength(5);
    expect(state.agents.opportunity_scout.status).toBe("waiting_for_workers");
    expect(state.agents.opportunity_scout.workers).toHaveLength(3);
    expect(state.agents.opportunity_scout.workers.every((worker) => worker.status === "completed")).toBe(true);
  });

  it("pauses on an approval and resumes after its decision", () => {
    const paused = reduceGraphEvents(DEMO_EVENTS.slice(0, 24));
    expect(paused.runState).toBe("awaiting_user");
    expect(paused.pendingApproval?.kind).toBe("shortlist_selection");
    expect(paused.agents.career_coordinator.status).toBe("waiting_for_approval");

    const resumed = reduceGraphEvents(DEMO_EVENTS.slice(0, 25));
    expect(resumed.runState).toBe("resuming");
    expect(resumed.pendingApproval).toBeNull();
  });

  it("deduplicates replayed SSE events by event_id", () => {
    const first = DEMO_EVENTS[0];
    const state = reduceGraphEvents([first, first]);
    expect(state.eventsApplied).toBe(1);
    expect(state.lastSequence).toBe(1);
  });

});

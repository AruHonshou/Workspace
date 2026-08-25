import { useEffect, useMemo, useRef, useState } from "react";
import { RunEventStream, type StreamConnectionState } from "../api/client";
import { reduceGraphEvents } from "../state/graphEvents";
import type { GraphEvent } from "../types";

export type TimelineMode = "live" | "replay";

export function useGraphRuntime(initialEvents: GraphEvent[], reducedMotion: boolean) {
  const [events, setEvents] = useState(initialEvents);
  const [mode, setMode] = useState<TimelineMode>("live");
  const [cursor, setCursor] = useState(initialEvents.length);
  const [playing, setPlaying] = useState(false);
  const [connection, setConnection] = useState<StreamConnectionState | "demo">("demo");
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const streamRef = useRef<RunEventStream | null>(null);

  useEffect(() => () => streamRef.current?.stop(), []);

  useEffect(() => {
    if (!playing || mode !== "replay" || reducedMotion) return;
    if (cursor >= events.length) {
      setPlaying(false);
      return;
    }
    const timer = window.setTimeout(() => setCursor((value) => Math.min(value + 1, events.length)), 620);
    return () => window.clearTimeout(timer);
  }, [cursor, events.length, mode, playing, reducedMotion]);

  const visibleEvents = mode === "live" ? events : events.slice(0, cursor);
  const state = useMemo(() => reduceGraphEvents(visibleEvents), [visibleEvents]);

  function appendEvent(event: GraphEvent): void {
    setEvents((current) => {
      if (current.some((item) => item.event_id === event.event_id)) return current;
      return [...current, event].sort((left, right) => left.sequence - right.sequence);
    });
  }

  function connectToRun(runId: string): void {
    streamRef.current?.stop();
    const stream = new RunEventStream();
    streamRef.current = stream;
    setEvents([]);
    setCursor(0);
    setMode("live");
    setPlaying(false);
    setActiveRunId(runId);
    stream.start(runId, {
      onEvent: appendEvent,
      onStatus: setConnection,
      onError: () => setConnection("error"),
    });
  }

  function enterReplay(): void {
    setMode("replay");
    setCursor(Math.max(1, events.length));
    setPlaying(false);
  }

  function jumpToLive(): void {
    setMode("live");
    setCursor(events.length);
    setPlaying(false);
  }

  function restartReplay(): void {
    setMode("replay");
    setCursor(events.length > 0 ? 1 : 0);
    setPlaying(!reducedMotion);
  }

  function setReplayCursor(value: number): void {
    setMode("replay");
    setPlaying(false);
    setCursor(Math.max(0, Math.min(value, events.length)));
  }

  return {
    activeRunId,
    connection,
    events,
    visibleEvents,
    state,
    mode,
    cursor: mode === "live" ? events.length : cursor,
    playing,
    connectToRun,
    enterReplay,
    jumpToLive,
    restartReplay,
    setReplayCursor,
    setPlaying,
    injectEvent: appendEvent,
  };
}

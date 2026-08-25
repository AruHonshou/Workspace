import type { Translate } from "../i18n";
import type { TimelineMode } from "../hooks/useGraphRuntime";

interface ReplayControlsProps {
  t: Translate;
  mode: TimelineMode;
  cursor: number;
  total: number;
  playing: boolean;
  reducedMotion: boolean;
  onReplay: () => void;
  onLive: () => void;
  onCursor: (value: number) => void;
  onPlaying: (value: boolean) => void;
}

export function ReplayControls({ t, mode, cursor, total, playing, reducedMotion, onReplay, onLive, onCursor, onPlaying }: ReplayControlsProps) {
  return (
    <section className="replay-controls surface" aria-labelledby="replay-title">
      <div className="replay-heading">
        <div>
          <span className="eyebrow">GraphEvent</span>
          <h2 id="replay-title">{t("replay.title")}</h2>
        </div>
        <span className={`mode-pill mode-${mode}`}>{t(`replay.mode.${mode}`)}</span>
      </div>
      <div className="timeline-row">
        <button type="button" className="icon-button" onClick={() => onCursor(cursor - 1)} disabled={cursor <= 0} aria-label={t("replay.previous")}>←</button>
        <button
          type="button"
          className="icon-button play-button"
          onClick={() => mode === "live" ? onReplay() : onPlaying(!playing)}
          aria-label={mode === "live" ? t("replay.replay") : playing ? t("replay.pause") : t("replay.play")}
          disabled={reducedMotion && mode === "replay"}
        >
          {mode === "live" ? "↺" : playing ? "Ⅱ" : "▶"}
        </button>
        <input
          type="range"
          min={0}
          max={Math.max(total, 1)}
          value={cursor}
          onChange={(event) => onCursor(Number(event.target.value))}
          aria-label={t("replay.title")}
        />
        <button type="button" className="icon-button" onClick={() => onCursor(cursor + 1)} disabled={cursor >= total} aria-label={t("replay.next")}>→</button>
      </div>
      <div className="timeline-meta">
        <span>{t("replay.event", { current: cursor, total })}</span>
        {mode === "replay" && <button type="button" className="text-button" onClick={onLive}>{t("replay.live")}</button>}
      </div>
    </section>
  );
}

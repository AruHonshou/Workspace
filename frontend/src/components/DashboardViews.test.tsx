import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { createTranslator } from "../i18n";
import { SearchView } from "./DashboardViews";
import { ResultsView } from "./DashboardViews";
import type { JobRecord } from "../types";

const t = createTranslator("es");

describe("Career search", () => {
  it("asks only for a role and starts with the confirmed profile", async () => {
    const onStart = vi.fn(async () => undefined);
    render(<SearchView profileReady deepSeekReady t={t} locale="es" onStart={onStart} onManualImport={vi.fn(async () => undefined)} />);

    await userEvent.type(screen.getByLabelText("Nombre del puesto"), "QA");
    await userEvent.click(screen.getByRole("button", { name: "Buscar ahora" }));

    await waitFor(() => expect(onStart).toHaveBeenCalledWith("QA"));
    expect(screen.getByText(/últimos 30 días/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Costa Rica/).length).toBeGreaterThanOrEqual(1);
  });

  it("blocks searching until the résumé is confirmed", async () => {
    const onStart = vi.fn(async () => undefined);
    render(<SearchView profileReady={false} deepSeekReady t={t} locale="es" onStart={onStart} onManualImport={vi.fn(async () => undefined)} />);

    await userEvent.type(screen.getByLabelText("Nombre del puesto"), "Desarrollador");
    expect(screen.getByRole("button", { name: "Buscar ahora" })).toBeDisabled();
    expect(screen.getByText(/confirmar tu CV/i)).toBeInTheDocument();
    expect(onStart).not.toHaveBeenCalled();
  });
});

describe("Stored result filters", () => {
  it("switches 24 hours, 7 days, and 30 days without another search", async () => {
    const anchor = "2026-08-20T18:00:00Z";
    const job = (id: string, ageHours: number): JobRecord => ({
      id,
      company: `Company ${id}`,
      title: `QA ${id}`,
      location: "Remote - LATAM",
      workMode: "remote",
      source: "jobicy",
      sources: ["jobicy"],
      verificationLevel: "authorized_feed",
      publishedAt: new Date(Date.parse(anchor) - ageHours * 3_600_000).toISOString(),
      officialApplyUrl: `https://jobs.example/${id}`,
      applyUrlType: "company",
      description: "QA role",
      requirements: [],
      fitScore: 70,
      fitLevel: "high",
      evidence: [],
      gaps: [],
    });
    render(<ResultsView jobs={[job("today", 12), job("week", 72), job("month", 480)]} analyses={{}} busyJob={null} aliases={[]} coverageIncomplete={false} referenceTime={anchor} t={t} locale="es" onAnalysis={vi.fn(async () => undefined)} onInterest={vi.fn(async () => undefined)} />);

    expect(screen.getAllByRole("heading", { level: 3 })).toHaveLength(3);
    await userEvent.click(screen.getByRole("button", { name: /24 h/i }));
    expect(screen.getAllByRole("heading", { level: 3 })).toHaveLength(1);
    expect(screen.getByText("QA today")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /7 días/i }));
    expect(screen.getAllByRole("heading", { level: 3 })).toHaveLength(2);
  });
});

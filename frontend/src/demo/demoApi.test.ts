import { describe, expect, it } from "vitest";

import { handleDemoRequest } from "./demoApi";

describe("GitHub Pages visual demo", () => {
  it("provides a complete fictitious professional profile", async () => {
    const profiles = await handleDemoRequest<Array<Record<string, unknown>>>("/api/profiles");

    expect(profiles).toHaveLength(1);
    expect(profiles[0]).toMatchObject({
      display_name: "QA Automation",
      name: "Sofía Ramírez",
      confirmed: true,
    });
  });

  it("returns cached sample jobs without contacting a provider", async () => {
    const result = await handleDemoRequest<{ cached: boolean; jobs: unknown[] }>("/api/searches", {
      method: "POST",
    });

    expect(result.cached).toBe(true);
    expect(result.jobs).toHaveLength(3);
  });

  it("shows all LinkedIn proposal sections", async () => {
    const proposals = await handleDemoRequest<Array<{ sections: Array<{ section: string }> }>>(
      "/api/linkedin/imports/demo_linkedin_snapshot/optimizations",
    );

    expect(proposals[0].sections.map((item) => item.section)).toEqual([
      "headline",
      "about",
      "experience",
      "education",
      "skills",
      "certifications",
    ]);
  });

  it("fails explicitly when a screen requests an unsupported endpoint", async () => {
    await expect(handleDemoRequest("/api/not-implemented")).rejects.toThrow(
      "Demo route not implemented",
    );
  });
});

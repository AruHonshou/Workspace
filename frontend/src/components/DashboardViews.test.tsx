import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { createTranslator } from "../i18n";
import { ProfileView, FilterSelect } from "./DashboardViews";
import type { CandidateProfile } from "../types";

const t = createTranslator("es");
const readyProfile: CandidateProfile = {
  id: "profile_qa",
  displayName: "QA",
  name: "Ada",
  headline: "QA engineer",
  location: "Costa Rica",
  targetRoles: ["QA"],
  revision: 1,
  completion: 100,
  confirmed: true,
  facts: [],
  resumes: {},
  preferences: { desiredTitles: ["QA"], targetSeniorities: [], allowedWorkModes: [], desiredLocations: ["Costa Rica"], excludedKeywords: [], excludedSectors: [] },
};

describe("Professional profiles", () => {
  it("keeps the profile dialog open and explains a rejected create", async () => {
    const onCreateProfile = vi.fn(async () => {
      throw new Error("A professional profile with this name already exists");
    });
    render(<ProfileView
      profile={readyProfile}
      profiles={[readyProfile]}
      t={t}
      locale="es"
      onSelectProfile={vi.fn(async () => undefined)}
      onCreateProfile={onCreateProfile}
      onRenameProfile={vi.fn(async () => undefined)}
      onDuplicateProfile={vi.fn(async () => undefined)}
      onDeleteProfile={vi.fn(async () => undefined)}
      onUpdatePreferences={vi.fn(async () => undefined)}
      onImport={vi.fn(async () => undefined)}
      onUpdateFact={vi.fn(async () => undefined)}
      onConfirm={vi.fn(async () => undefined)}
      onReprocess={vi.fn(async () => undefined)}
      onCloudConsent={vi.fn(async () => undefined)}
    />);

    await userEvent.click(screen.getByRole("button", { name: /Nuevo/i }));
    await userEvent.type(screen.getByPlaceholderText("Ej. QA Automation"), "QA existente");
    await userEvent.click(screen.getByRole("button", { name: "Guardar" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("already exists");
    expect(screen.getByRole("dialog", { name: "Administrar perfil" })).toBeInTheDocument();
    expect(onCreateProfile).toHaveBeenCalledOnce();
  });
});

describe("Shared profile selectors", () => {
  it("allows keyboard selection and Escape dismissal", async () => {
    const onChange = vi.fn();
    render(<FilterSelect icon="▣" label="Perfil" ariaLabel="Perfil" value="qa"
      options={[{value:"qa",label:"QA"},{value:"dev",label:"Desarrollo"}]} onChange={onChange} />);
    const trigger = screen.getByRole("button", {name: /Perfil: QA/});
    await userEvent.click(trigger);
    expect(screen.getByRole("listbox", {name:"Perfil"})).toBeVisible();
    await userEvent.keyboard("{ArrowDown}{Enter}");
    expect(onChange).toHaveBeenCalledWith("dev");
    await userEvent.click(trigger);
    await userEvent.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("listbox")).not.toBeInTheDocument());
    expect(trigger).toHaveFocus();
  });
});

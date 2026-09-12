import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useLayoutEffect, type RefObject } from "react";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { DESK_LOOK_LIMIT, type DeskLook } from "../components/deskSceneCamera";
import { DesktopShell } from "./DesktopShell";

type MockSceneProps = {
  phase: string;
  onUnavailable: () => void;
  onReady: () => void;
  look: RefObject<DeskLook>;
  requestFrame: RefObject<(() => void) | null>;
  screenElement: RefObject<HTMLElement | null>;
};
const sceneHarness = vi.hoisted(() => ({ props: null as MockSceneProps | null, invalidate: vi.fn() }));

vi.mock("../components/DeskScene", () => ({
  DeskScene: (props: MockSceneProps) => {
    sceneHarness.props = props;
    useLayoutEffect(() => {
      props.requestFrame.current = sceneHarness.invalidate;
      props.onReady();
      return () => { props.requestFrame.current = null; };
    }, [props.onReady, props.requestFrame]);
    return <div data-testid="desk-render" data-phase={props.phase}>
      <button onClick={props.onUnavailable}>Graphics unavailable</button>
      <input aria-label="Scene input" />
      <a href="#desktop-home">Scene link</a>
    </div>;
  },
}));

beforeEach(() => { sceneHarness.props = null; sceneHarness.invalidate.mockClear(); });

function pointer(target: Element, type: string, x: number, y: number, pointerId = 1) {
  const event = new MouseEvent(type, { bubbles: true, cancelable: true, button: 0, clientX: x, clientY: y });
  Object.defineProperty(event, "pointerId", { value: pointerId });
  fireEvent(target, event);
}

function mount(path = "/") {
  return render(<MemoryRouter initialEntries={[path]}><DesktopShell locale="es" onLocaleChange={vi.fn()}
    renderView={(view) => <label>{view}<input aria-label={`Draft ${view}`} defaultValue="" /></label>}
    notice={null} onDismissNotice={vi.fn()} /></MemoryRouter>);
}

function allowMotion() {
  vi.spyOn(window, "matchMedia").mockImplementation((query) => ({
    matches: false, media: query, onchange: null,
    addListener: vi.fn(), removeListener: vi.fn(), addEventListener: vi.fn(), removeEventListener: vi.fn(), dispatchEvent: vi.fn(),
  }));
}

describe("Original desktop and browser shell", () => {
  it("places the live welcome and navigation action inside the monitor screen", async () => {
    const { container } = mount();
    await screen.findByTestId("desk-render");
    const monitor = container.querySelector<HTMLElement>(".monitor-home")!;
    expect(within(monitor).getByRole("heading", { name: "Un espacio para lo que sigue." })).toBeVisible();
    expect(within(monitor).getByRole("link", { name: "Explorar oportunidades" })).toHaveAttribute("href", "/buscar");
    expect(sceneHarness.props?.screenElement.current).toBe(monitor);
    expect(container.querySelector(".desktop-shell")).toHaveClass("pov-ready");
    expect(container.querySelector(".desktop-dock-area")).toBeNull();
    expect(screen.queryByRole("navigation")).not.toBeInTheDocument();
    expect(screen.queryByText("Arrastra para mirar alrededor")).not.toBeInTheDocument();
  });

  it("associates the coffee and mouse with the exact owner profiles without navigating on hover", async () => {
    const user = userEvent.setup();
    mount();
    const coffee = screen.getByRole("link", { name: "Taza de café: abrir LinkedIn de Kendall Valverde" });
    const mouse = screen.getByRole("link", { name: "Ratón: abrir GitHub de AruHonshou" });
    const notebook = screen.getByRole("link", { name: "Cuaderno: abrir portfolio de AruHonshou" });
    expect(coffee).toHaveAttribute("href", "https://www.linkedin.com/in/kendall-valverde-diaz-aru/");
    expect(mouse).toHaveAttribute("href", "https://github.com/AruHonshou");
    expect(notebook).toHaveAttribute("href", "https://aruhonshou.github.io/Aru/portfolio.html");
    for (const link of [coffee, mouse, notebook]) {
      expect(link).toHaveAttribute("target", "_blank");
      expect(link).toHaveAttribute("rel", "noopener noreferrer");
    }
    const open = vi.spyOn(window, "open").mockImplementation(() => null);
    await user.hover(coffee);
    await user.hover(mouse);
    await user.hover(notebook);
    expect(open).not.toHaveBeenCalled();
    expect(screen.getByRole("heading", { name: "Un espacio para lo que sigue." })).toBeVisible();
  });

  it("enables limited view controls when the scene is ready and requests demand-rendered frames", async () => {
    mount();
    const right = screen.getByRole("button", { name: "Mirar a la derecha" });
    await waitFor(() => expect(right).toBeEnabled());
    for (let i = 0; i < 10; i++) fireEvent.click(right);
    expect(sceneHarness.props?.look.current).toEqual({ yaw: DESK_LOOK_LIMIT.yaw, pitch: 0 });
    expect(sceneHarness.invalidate).toHaveBeenCalledTimes(10);
    for (let i = 0; i < 10; i++) fireEvent.click(screen.getByRole("button", { name: "Mirar a la izquierda" }));
    expect(sceneHarness.props?.look.current).toEqual({ yaw: -DESK_LOOK_LIMIT.yaw, pitch: 0 });
    fireEvent.click(screen.getByRole("button", { name: "Centrar vista" }));
    expect(sceneHarness.props?.look.current).toEqual({ yaw: 0, pitch: 0 });
    fireEvent.click(screen.getByRole("button", { name: "Graphics unavailable" }));
    expect(right).toBeDisabled();
    expect(screen.getByRole("button", { name: "Centrar vista" })).toBeDisabled();
  });

  it("scopes arrow-key head movement to the focused stage instead of stealing form input", async () => {
    const user = userEvent.setup();
    mount();
    await screen.findByTestId("desk-render");
    const stage = screen.getByRole("region", { name: "Mover la vista del escritorio" });
    stage.focus();
    expect(stage).toHaveFocus();
    await user.keyboard("{ArrowRight}{ArrowUp}");
    expect(sceneHarness.props?.look.current).toEqual({ yaw: .07, pitch: .045 });
    const before = { ...sceneHarness.props!.look.current };
    const rendered = sceneHarness.invalidate.mock.calls.length;
    await user.click(screen.getByRole("textbox", { name: "Scene input" }));
    await user.keyboard("QA{ArrowLeft}{ArrowDown}{Home}{Escape}");
    expect(screen.getByRole("textbox", { name: "Scene input" })).toHaveValue("QA");
    expect(sceneHarness.props?.look.current).toEqual(before);
    expect(sceneHarness.invalidate).toHaveBeenCalledTimes(rendered);
    stage.focus();
    await user.keyboard("{Home}");
    expect(sceneHarness.props?.look.current).toEqual({ yaw: 0, pitch: 0 });
  });

  it("clamps pointer look, ignores other pointers, and stops dragging on cancellation", async () => {
    mount();
    await screen.findByTestId("desk-render");
    const stage = screen.getByRole("region", { name: "Mover la vista del escritorio" });
    pointer(stage, "pointerdown", 100, 100);
    pointer(stage, "pointermove", 1000, 1000, 2);
    expect(sceneHarness.props?.look.current).toEqual({ yaw: 0, pitch: 0 });
    pointer(stage, "pointermove", 1000, 1000);
    expect(sceneHarness.props?.look.current).toEqual({ yaw: -DESK_LOOK_LIMIT.yaw, pitch: DESK_LOOK_LIMIT.pitch });
    pointer(stage, "pointercancel", 1000, 1000);
    pointer(stage, "pointermove", -1000, -1000);
    expect(sceneHarness.props?.look.current).toEqual({ yaw: -DESK_LOOK_LIMIT.yaw, pitch: DESK_LOOK_LIMIT.pitch });
    expect(sceneHarness.invalidate).toHaveBeenCalledTimes(1);
  });

  it("does not begin pointer drags from interactive scene descendants", async () => {
    mount();
    await screen.findByTestId("desk-render");
    const stage = screen.getByRole("region", { name: "Mover la vista del escritorio" });
    for (const target of [
      screen.getByRole("button", { name: "Graphics unavailable" }),
      screen.getByRole("textbox", { name: "Scene input" }),
      screen.getByRole("link", { name: "Scene link" }),
    ]) {
      pointer(target, "pointerdown", 100, 100);
      pointer(stage, "pointermove", 900, 900);
      pointer(stage, "pointerup", 900, 900);
    }
    expect(sceneHarness.props?.look.current).toEqual({ yaw: 0, pitch: 0 });
    expect(sceneHarness.invalidate).not.toHaveBeenCalled();
  });

  it("resets the home look when entering a page and keeps keyboard arrows in that page's form", async () => {
    const user = userEvent.setup();
    mount();
    await waitFor(() => expect(screen.getByRole("button", { name: "Mirar a la derecha" })).toBeEnabled());
    await user.click(screen.getByRole("button", { name: "Mirar a la derecha" }));
    expect(sceneHarness.props?.look.current.yaw).toBe(.15);
    await user.click(screen.getByRole("link", { name: "Explorar oportunidades" }));
    expect(sceneHarness.props?.look.current).toEqual({ yaw: 0, pitch: 0 });
    const rendered = sceneHarness.invalidate.mock.calls.length;
    await user.type(screen.getByLabelText("Draft search"), "QA{ArrowLeft}{ArrowRight}");
    expect(screen.getByLabelText("Draft search")).toHaveValue("QA");
    expect(sceneHarness.invalidate).toHaveBeenCalledTimes(rendered);
  });

  it("enters through the monitor without a dock or audio and shows accessible browser tabs", async () => {
    const user = userEvent.setup();
    const { container } = mount();
    expect(screen.getByRole("heading", { name: "Un espacio para lo que sigue." })).toBeVisible();
    expect(container.querySelector("audio")).toBeNull();
    expect(screen.queryByRole("button", { name: /Entrar a/ })).not.toBeInTheDocument();
    await user.click(screen.getByRole("link", { name: "Explorar oportunidades" }));
    expect(container.querySelector(".desktop-shell")).toHaveAttribute("data-phase", "working");
    expect(container.querySelector(".desktop-home-layer")).toHaveAttribute("inert");
    expect(container.querySelector(".browser-workspace")).not.toHaveAttribute("inert");
    expect(screen.getAllByRole("navigation")).toHaveLength(1);
    expect(screen.getByRole("heading", { name: "Buscar empleos" })).toHaveFocus();
  });

  it("keeps drafts across tabs and Home without replaying an entry screen", async () => {
    const user = userEvent.setup();
    mount("/buscar");
    await user.type(screen.getByLabelText("Draft search"), "QA Automation");
    await user.click(screen.getByRole("link", { name: "LinkedIn" }));
    await user.click(screen.getByRole("link", { name: "Inicio" }));
    await user.click(screen.getByRole("link", { name: "Explorar oportunidades" }));
    expect(screen.getByLabelText("Draft search")).toHaveValue("QA Automation");
    expect(screen.getByRole("heading", { name: "Buscar empleos" })).toHaveFocus();
  });

  it("offers an animation skip in both directions and never exposes forms mid-transition", async () => {
    allowMotion();
    const user = userEvent.setup();
    const { container } = mount();
    await user.click(screen.getByRole("link", { name: "Explorar oportunidades" }));
    expect(container.querySelector(".desktop-shell")).toHaveAttribute("data-phase", "entering");
    expect(container.querySelector(".browser-workspace")).toHaveAttribute("inert");
    await user.click(screen.getByRole("button", { name: "Omitir animación" }));
    expect(container.querySelector(".desktop-shell")).toHaveAttribute("data-phase", "working");
    await user.click(screen.getByRole("link", { name: "Inicio" }));
    expect(container.querySelector(".desktop-shell")).toHaveAttribute("data-phase", "leaving");
    await user.click(screen.getByRole("button", { name: "Omitir animación" }));
    expect(container.querySelector(".desktop-shell")).toHaveAttribute("data-phase", "home");
    expect(screen.getByRole("heading", { name: "Un espacio para lo que sigue." })).toHaveFocus();
  });

  it("opens pages even if WebGL fails and remembers the optional camera setting", async () => {
    allowMotion();
    const user = userEvent.setup();
    const { container } = mount();
    await screen.findByTestId("desk-render");
    await user.click(screen.getByRole("button", { name: "Graphics unavailable" }));
    await user.click(screen.getByRole("button", { name: "Animaciones de cámara" }));
    expect(localStorage.getItem("workspace-static-view")).toBe("true");
    await user.click(screen.getByRole("link", { name: "Explorar oportunidades" }));
    await waitFor(() => expect(container.querySelector(".desktop-shell")).toHaveAttribute("data-phase", "working"));
    expect(screen.queryByRole("button", { name: "Omitir animación" })).not.toBeInTheDocument();
  });
});

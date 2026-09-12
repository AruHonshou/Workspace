import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { FactDisclosure } from "./FactDisclosure";
import { EditorialQuote } from "./EditorialQuote";

describe("progressive evidence disclosure", () => {
  it("starts collapsed, keeps every row mounted, and exposes overflow without losing edits", async () => {
    const edit = vi.fn();
    const { container } = render(<FactDisclosure title="Experiencia" verified={8} locale="es">
      {Array.from({ length: 10 }, (_, index) => <article key={index}>
        <p>Hecho {index + 1}</p><input aria-label={`Texto ${index + 1}`} defaultValue={`Original ${index + 1}`} />
        <button onClick={() => edit(index)}>Editar {index + 1}</button>
      </article>)}
    </FactDisclosure>);
    const group = container.querySelector(".fact-category")!;
    const more = container.querySelector(".fact-overflow")!;
    expect(group).not.toHaveAttribute("open");
    expect(container.querySelectorAll("article")).toHaveLength(10);
    expect(screen.getByText("Hecho 1")).not.toBeVisible();
    await userEvent.click(screen.getByText("Experiencia"));
    expect(group).toHaveAttribute("open");
    expect(screen.getByText("Hecho 6")).toBeVisible();
    expect(screen.getByText("Hecho 7")).not.toBeVisible();
    await userEvent.click(screen.getByText("Ver 4 más"));
    expect(more).toHaveAttribute("open");
    expect(screen.getByText("Hecho 10")).toBeVisible();
    await userEvent.type(screen.getByLabelText("Texto 10"), " editado");
    await userEvent.click(screen.getByRole("button", { name: "Editar 10" }));
    expect(edit).toHaveBeenCalledWith(9);
    await userEvent.click(screen.getByText("Experiencia"));
    await userEvent.click(screen.getByText("Experiencia"));
    expect(screen.getByLabelText("Texto 10")).toHaveValue("Original 10 editado");
    expect(container.querySelectorAll("article")).toHaveLength(10);
  });

  it("does not add a more control for a short category and translates metadata", async () => {
    const { container } = render(<FactDisclosure title="Skills" verified={1} locale="en">
      {[<article key="one">Playwright</article>]}
    </FactDisclosure>);
    expect(screen.getByText("✓ 1 reviewed")).toBeInTheDocument();
    expect(container.querySelector(".fact-overflow")).not.toBeInTheDocument();
    await userEvent.click(screen.getByText("Skills"));
    expect(screen.getByText("Playwright")).toBeVisible();
  });
});

describe("editorial headers", () => {
  it("follows existing routes and ES/EN without creating navigation", () => {
    const { rerender, container } = render(<EditorialQuote path="/favoritos/saved_existing" locale="es" />);
    expect(container).toHaveTextContent("Buenas oportunidades llevan a grandes historias.");
    rerender(<EditorialQuote path="/favoritos" locale="en" />);
    expect(container).toHaveTextContent("Great opportunities lead to great stories.");
    expect(container.querySelector("a")).toBeNull();
    rerender(<EditorialQuote path="/" locale="es" />);
    expect(container).toBeEmptyDOMElement();
  });
});

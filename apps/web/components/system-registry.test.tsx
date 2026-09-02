import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { fixtureSystems } from "@/lib/fixtures";
import { SystemRegistry } from "./system-registry";

describe("SystemRegistry", () => {
  it("filters by owner and keeps an instructive empty state", () => {
    render(<SystemRegistry systems={fixtureSystems} />);
    const filter = screen.getByRole("searchbox", { name: "Filter systems" });
    fireEvent.change(filter, { target: { value: "Ana Silva" } });
    expect(screen.getAllByRole("article")).toHaveLength(2);
    fireEvent.change(filter, { target: { value: "no match" } });
    expect(
      screen.getByText("No system matches that evidence trail."),
    ).toBeInTheDocument();
  });
});

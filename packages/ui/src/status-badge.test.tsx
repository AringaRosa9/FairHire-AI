import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StatusBadge } from "./status-badge";

describe("StatusBadge", () => {
  it("communicates status in text as well as color", () => {
    render(<StatusBadge tone="review">Review required</StatusBadge>);
    expect(screen.getByText("Review required")).toHaveAttribute(
      "data-tone",
      "review",
    );
  });
});

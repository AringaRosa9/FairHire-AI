import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { FirstAuditWizard } from "./first-audit-wizard";

describe("FirstAuditWizard", () => {
  beforeEach(() => window.localStorage.clear());

  it("blocks incomplete registration and explains the missing evidence", async () => {
    render(<FirstAuditWizard />);
    fireEvent.click(screen.getByRole("button", { name: "Continue →" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Enter a system name",
    );
  });

  it("restores a local draft without retaining file bytes", async () => {
    window.localStorage.setItem(
      "fairhire:first-audit",
      JSON.stringify({
        name: "Restored screening system",
        step: 2,
        fileName: "decisions.csv",
      }),
    );
    render(<FirstAuditWizard />);
    expect(
      await screen.findByRole("heading", {
        name: "Which output will be tested?",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("decisions.csv")).toBeInTheDocument();
    expect(
      screen.getByText(/draft remembers metadata, not local file bytes/i),
    ).toBeInTheDocument();
  });
});

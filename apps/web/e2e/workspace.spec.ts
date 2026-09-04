import { expect, test } from "@playwright/test";

test("portfolio exposes release evidence and primary navigation", async ({
  page,
}) => {
  await page.goto("/portfolio");
  await expect(
    page.getByRole("heading", { name: "What needs a human decision?" }),
  ).toBeVisible();
  await expect(
    page.getByText("Blocked", { exact: true }).first(),
  ).toBeVisible();
});

test("mobile systems registry keeps filtering and risk status available", async ({
  page,
}, testInfo) => {
  test.skip(
    !testInfo.project.name.includes("mobile"),
    "mobile-only adaptation check",
  );
  await page.goto("/systems");
  await expect(
    page.getByRole("searchbox", { name: "Filter systems" }),
  ).toBeVisible();
  await expect(page.getByText("Do not use")).toBeVisible();
  await page.getByRole("button", { name: "Open navigation" }).click();
  await expect(page.getByRole("navigation")).toBeVisible();
  await expect(page.getByRole("link", { name: /Systems/ })).toBeVisible();
});

test("first audit restores a real registration draft", async ({ page }) => {
  await page.goto("/onboarding");
  await expect(
    page.getByRole("heading", { name: "Build an evidence-ready check" }),
  ).toBeVisible();
  await page.getByLabel("System name").fill("Restorable screening review");
  await page
    .getByLabel("Intended purpose")
    .fill("Prioritizes applications for a human recruiter to review");
  await page.reload();
  await expect(page.getByLabel("System name")).toHaveValue(
    "Restorable screening review",
  );
  await expect(
    page.getByText(/Draft restored from this device/i),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
});

test("governance register exposes traceability and the release approval chain", async ({
  page,
}) => {
  await page.goto("/findings");
  await expect(
    page.getByRole("heading", { name: "Problems that need someone to act" }),
  ).toBeVisible();
  await expect(
    page.getByText("Control mapping", { exact: true }).first(),
  ).toHaveCount(0);
  await page
    .getByRole("link", { name: "Career gaps may reduce selection for women" })
    .click();
  await expect(
    page.getByText("Control mapping", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText("POL-FR-02 §4.2")).toBeVisible();

  await page.goto("/approvals");
  await expect(
    page.getByRole("heading", { name: "Release approval center" }),
  ).toBeVisible();
  await expect(page.getByText("Responsible AI", { exact: true })).toBeVisible();
  await expect(page.getByText("Legal / DPO", { exact: true })).toBeVisible();
});

test("due-task queue keeps completion evidence next to ownership", async ({
  page,
}) => {
  await page.goto("/tasks");
  await expect(
    page.getByRole("heading", { name: "Work due before release" }),
  ).toBeVisible();
  await expect(page.getByText("Jon Bell", { exact: true })).toBeVisible();
  await expect(page.getByText("Overdue", { exact: true })).toBeVisible();
});

test("evidence package and read-only assistant expose their safety boundaries", async ({
  page,
}) => {
  await page.goto("/reports");
  await expect(
    page.getByRole("heading", { name: "Reports traceable to their source" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Create evidence package" }),
  ).toBeVisible();
  await expect(page.getByLabel("Completed Audit Run ID")).toBeVisible();

  await page.goto("/assistant");
  await expect(
    page.getByRole("heading", { name: "Compliance help that shows its work" }),
  ).toBeVisible();
  await expect(page.getByText("Write tools")).toBeVisible();
  await expect(page.getByText("None", { exact: true })).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Question" })).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
});

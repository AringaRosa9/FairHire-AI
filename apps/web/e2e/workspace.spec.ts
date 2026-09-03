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

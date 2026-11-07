// Computed text contrast inspection, not a full accessibility audit.
async function inspectHrPortalContrast(page) {
  const pages = [];
  async function inspect(path) {
    const results = await page.evaluate(() => {
      const rgb = (text) => (text.match(/[\d.]+/g) || []).map(Number);
      const luminance = (color) =>
        color
          .slice(0, 3)
          .map((v) => v / 255)
          .map((v) => (v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4))
          .reduce((sum, v, i) => sum + v * [0.2126, 0.7152, 0.0722][i], 0);
      const groups = {};
      for (const el of document.querySelectorAll(".p-app *, .p-login *")) {
        const text = Array.from(el.childNodes)
          .filter((node) => node.nodeType === 3)
          .map((node) => node.textContent)
          .join("")
          .trim();
        if (
          !text ||
          !el.checkVisibility() ||
          el.closest("[disabled],.p-sr-only")
        )
          continue;
        let current = el,
          background = [255, 255, 255, 1];
        while (current) {
          const value = rgb(getComputedStyle(current).backgroundColor);
          if (value.length >= 3 && (value.length < 4 || value[3] >= 0.99)) {
            background = value;
            break;
          }
          current = current.parentElement;
        }
        const style = getComputedStyle(el),
          color = rgb(style.color);
        const a = luminance(color),
          b = luminance(background),
          ratio = (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
        const large =
          parseFloat(style.fontSize) >= 24 ||
          (parseFloat(style.fontSize) >= 18.66 &&
            parseFloat(style.fontWeight) >= 700);
        if (ratio < (large ? 3 : 4.5)) {
          const key = style.color + " on " + background.slice(0, 3).join(",");
          if (!groups[key])
            groups[key] = { ratio: +ratio.toFixed(2), samples: [] };
          if (groups[key].samples.length < 2)
            groups[key].samples.push({
              text: text.slice(0, 65),
              selector: el.className,
              size: style.fontSize,
            });
        }
      }
      return {
        width: innerWidth,
        documentWidth: document.documentElement.scrollWidth,
        lowContrast: groups,
      };
    });
    pages.push({ path, ...results });
  }
  await inspect("/hr/assistant (actual answer state)");
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 1040 });
    for (const path of [
      "",
      "/benefits",
      "/assistant",
      "/library",
      "/preparations",
      "/profile",
      "/status",
    ]) {
      const links = await page.locator('a[href="/hr' + path + '"]').all();
      let found = false;
      for (const link of links)
        if (await link.isVisible()) {
          await link.click();
          found = true;
          break;
        }
      if (!found) throw Error("Missing route " + path);
      await page.getByRole("heading", { level: 1 }).waitFor();
      await page.evaluate(
        () =>
          new Promise((resolve) =>
            requestAnimationFrame(() => requestAnimationFrame(resolve)),
          ),
      );
      await inspect("/hr" + path);
    }
  }
  await page.setViewportSize({ width: 1440, height: 1040 });
  await page.getByRole("link", { name: "K:LINK 인사 홈", exact: true }).click();
  return {
    status: pages.every((p) => Object.keys(p.lowContrast).length === 0)
      ? "PASSED"
      : "NEEDS_REVIEW",
    scope:
      "Computed text foreground/background contrast only; not full accessibility compliance",
    pages,
  };
}

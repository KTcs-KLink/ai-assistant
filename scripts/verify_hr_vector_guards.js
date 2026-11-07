// Fill the marker with a retained actual response in an ignored generated file.
// All answer POSTs below are intercepted. No new model generation occurs.
async function verifyHrVectorGuards(page) {
  const original = /* RETAINED_ACTUAL_RESPONSE */ {};
  if (!original.retrieval?.matches?.length)
    throw Error(
      "Prepare the retained-response fixture first; no model calls made",
    );
  const base = "http://127.0.0.1:8825",
    route = base + "/api/benefits/hr/answer",
    checks = [],
    errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.setDefaultTimeout(20000);
  await page.unroute(route);
  await page.goto(base + "/hr");
  await page.getByRole("heading", { level: 1 }).waitFor();
  const login = page.getByRole("button", {
    name: "예시 직원으로 인사 기능 시작",
    exact: true,
  });
  if (await login.isVisible()) {
    await login.click();
    await page.locator('.hr-app[aria-busy="false"]').waitFor();
  }
  await page
    .getByRole("navigation", { name: "인사 포털 메뉴" })
    .getByRole("link", { name: "AI 업무 도우미", exact: true })
    .click();
  await page.locator("body").ariaSnapshot();
  try {
    for (const [name, change] of [
      [
        "changed actual chunk offset",
        (data) => data.retrieval.matches[0].start++,
      ],
      [
        "changed actual chunk hash",
        (data) => (data.retrieval.matches[0].sha256 = "0".repeat(64)),
      ],
      [
        "query embedding falsely marked cached",
        (data) => (data.retrieval.embedding.cached = true),
      ],
    ]) {
      const value = JSON.parse(JSON.stringify(original));
      value.validation = "FINAL_DETERMINISTIC_REVALIDATION_NOT_NEW_GENERATION";
      change(value);
      await page.unroute(route);
      await page.route(route, (request) =>
        request.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(value),
        }),
      );
      await page.getByRole("button", { name: "새 대화", exact: true }).click();
      await page
        .getByRole("textbox", { name: "서버 인사 질문", exact: true })
        .fill("일반 병가 원문 확인");
      await page
        .getByRole("button", { name: "서버에 인사 질문 보내기", exact: true })
        .click();
      await page.locator(".hr-conversation .hr-errors").waitFor();
      if (
        await page
          .locator(".hr-answer-part,.hr-condition-quote,.hr-retrieval-trace")
          .count()
      )
        throw Error("Unverified answer was rendered: " + name);
      checks.push({
        name,
        passed: true,
        mode: "intercepted tampering of retained actual response",
      });
    }
    if (errors.length) throw Error(errors.join("; "));
    return {
      status: "PASSED",
      checks,
      pageErrors: errors,
      paidModelCalls: 0,
      replay: true,
      scope:
        "Three browser integrity failure checks; not new model answers or semantic-quality grading",
    };
  } finally {
    await page.unroute(route);
  }
}

// Explicit retained-response replay and tampering checks; every answer POST is intercepted.
async function verifyHrCloseoutReplay(page) {
  const fixtures = /* RETAINED_CLOSEOUT_RESPONSES */ {};
  if (!fixtures.answer || !fixtures.withheld)
    throw Error("Prepare retained fixtures first; no model calls made");
  const base = "http://127.0.0.1:8825",
    route = base + "/api/benefits/hr/answer",
    checks = [],
    errors = [];
  const clone = (value) => JSON.parse(JSON.stringify(value));
  page.on("pageerror", (error) => errors.push(error.message));
  page.setDefaultTimeout(20000);
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
  async function show(value) {
    value.validation = "FINAL_DETERMINISTIC_REVALIDATION_NOT_NEW_GENERATION";
    await page.unroute(route);
    await page.route(route, (r) =>
      r.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(value),
      }),
    );
    await page.getByRole("button", { name: "새 대화", exact: true }).click();
    await page
      .getByRole("textbox", { name: "서버 인사 질문", exact: true })
      .fill("일반 인사 원문 확인");
    await page
      .getByRole("button", { name: "서버에 인사 질문 보내기", exact: true })
      .click();
    await page
      .getByRole("button", { name: "서버에 인사 질문 보내기", exact: true })
      .filter({ hasText: "질문 보내기" })
      .waitFor();
  }
  const check = (condition, message) => {
    if (!condition) throw Error(message);
  };
  try {
    await show(clone(fixtures.answer));
    await page.locator(".hr-answer-part").first().waitFor();
    await page.locator(".hr-quote-method").waitFor();
    await page
      .getByText("보존 응답 재생 · 새 모델 호출 아님", { exact: true })
      .waitFor();
    check(
      (await page.locator(".hr-answer-part").count()) ===
        fixtures.answer.paragraphs.length,
      "Retained answer missing",
    );
    checks.push({
      name: "retained application-restored answer",
      passed: true,
      mode: "actual response replay",
    });
    await show(clone(fixtures.withheld));
    await page.locator(".hr-withheld").waitFor();
    check(
      (await page.locator(".hr-answer-part").count()) === 0,
      "Withheld body was shown",
    );
    check(
      (await page.locator(".hr-answer-sources button").count()) ===
        fixtures.withheld.sources.length,
      "Withheld sources unavailable",
    );
    await page.getByText("추가 확인 필요", { exact: true }).waitFor();
    checks.push({
      name: "retained withheld answer remains review-only",
      passed: true,
      mode: "original backend final case 03-041 replay",
    });
    const partial = clone(fixtures.answer);
    partial.partial_verified_text = true;
    partial.status = "answered";
    await show(partial);
    await page.getByText("추가 확인 필요", { exact: true }).waitFor();
    checks.push({
      name: "partial flag cannot be promoted to answered",
      passed: true,
      mode: "explicit synthetic partial transport flag",
    });
    for (const [name, change] of [
      [
        "unsupported quote provenance",
        (d) => (d.quote_method = "MODEL_GENERATED_QUOTES"),
      ],
      [
        "quote absent from actual original",
        (d) =>
          (d.paragraphs[0].citations[0].quote =
            "실제 원문에 존재하지 않는 TEST 인용입니다."),
      ],
      [
        "changed source hash",
        (d) => (d.sources.at(-1).sha256 = "0".repeat(64)),
      ],
    ]) {
      const data = clone(fixtures.answer);
      change(data);
      await show(data);
      await page.locator(".hr-conversation .hr-errors").waitFor();
      check(
        (await page
          .locator(".hr-answer-part,.hr-condition-quote,.hr-retrieval-trace")
          .count()) === 0,
        "Unverified content rendered: " + name,
      );
      checks.push({ name, passed: true, mode: "tampered retained response" });
    }
    check(!errors.length, "Browser errors " + errors.join(";"));
    return {
      status: "PASSED",
      checks,
      pageErrors: errors,
      newModelGenerations: 0,
      replay: true,
      scope:
        "Bounded UI quote/source/withholding checks; not new model answers or semantic accuracy evaluation",
    };
  } finally {
    await page.unroute(route);
  }
}

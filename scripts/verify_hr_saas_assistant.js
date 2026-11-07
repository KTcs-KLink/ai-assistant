// Actual local source GETs plus explicitly retained/synthetic answer transport.
// Every answer POST is intercepted. No model generations in this script.
async function verifySaasAssistant(page) {
  const fixture = /* RETAINED_ASSISTANT_FIXTURE */ {};
  if (!fixture.response || !fixture.question)
    throw Error("Prepare retained response first; no model calls made");
  const base = "http://127.0.0.1:8825",
    api = base + "/api/benefits",
    route = api + "/hr/answer";
  const checks = [],
    widths = [],
    errors = [],
    requests = [];
  const clone = (value) => JSON.parse(JSON.stringify(value));
  const assert = (value, message) => {
    if (!value) throw Error(message);
  };
  const record = (name, mode = "retained response replay") =>
    checks.push({ name, mode, passed: true });
  let answerPosts = 0,
    response = clone(fixture.response),
    httpStatus = 200;
  response.validation = "FINAL_DETERMINISTIC_REVALIDATION_NOT_NEW_GENERATION";
  page.setDefaultTimeout(20000);
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.pathname.startsWith("/api/benefits"))
      requests.push({
        path: url.pathname,
        auth: !!request.headers().authorization,
      });
  });
  await page.addInitScript(() => {
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: {
        writeText: async (text) => {
          window.__qaCopiedAnswer = text;
        },
      },
    });
  });
  await page.route(route, (request) => {
    answerPosts++;
    return request.fulfill({
      status: httpStatus,
      contentType: "application/json",
      body: JSON.stringify(
        httpStatus === 200 ? response : { detail: "합성 연결 실패 검사" },
      ),
    });
  });
  async function ready() {
    await page.locator(".sa-assistant").waitFor();
    await page.locator("body").ariaSnapshot();
  }
  async function reset() {
    await page.getByRole("button", { name: "새 대화", exact: true }).click();
  }
  async function send(data, question = fixture.question, status = 200) {
    response = clone(data);
    httpStatus = status;
    if (status === 200)
      response.validation =
        "FINAL_DETERMINISTIC_REVALIDATION_NOT_NEW_GENERATION";
    await reset();
    await page
      .getByRole("textbox", { name: "인사 질문", exact: true })
      .fill(question);
    await page
      .getByRole("button", { name: "인사 질문 전송", exact: true })
      .click();
    await page
      .getByRole("button", { name: "인사 질문 전송", exact: true })
      .waitFor();
  }
  try {
    await page.setViewportSize({ width: 1440, height: 1040 });
    await page.goto(base + "/hr/assistant");
    const login = page.getByRole("button", {
      name: "예시 직원으로 인사 기능 시작",
      exact: true,
    });
    await page.getByRole("heading", { level: 1 }).waitFor();
    if (await login.isVisible()) {
      await login.click();
      await page.locator(".hr-saas").waitFor();
      await page.goto(base + "/hr/assistant");
    }
    await ready();
    const notice = page.getByRole("button", { name: "안내 닫기", exact: true });
    if (await notice.isVisible()) await notice.click();
    await page.locator(".sa-prompts button").first().click();
    assert(
      (
        await page
          .getByRole("textbox", { name: "인사 질문", exact: true })
          .inputValue()
      ).includes("진단서"),
      "Suggested question not drafted",
    );
    assert(answerPosts === 0, "Prompt auto-submitted");
    await reset();
    record(
      "Question suggestions draft without provider requests",
      "actual UI, no answer POST",
    );

    await page.getByRole("button", { name: "근거 자료", exact: true }).click();
    await page
      .getByRole("textbox", { name: "원문 검색어", exact: true })
      .fill("휴가");
    const searched = page.waitForResponse(
      (r) =>
        r.url().includes("/hr/evidence?q=") && r.request().method() === "GET",
    );
    await page
      .locator(".sa-source-search")
      .getByRole("button", { name: "검색", exact: true })
      .click();
    const searchResponse = await searched,
      searchData = await searchResponse.json();
    assert(
      searchResponse.status() === 200 &&
        searchData.company === "KEPCO" &&
        searchData.results.length,
      "Actual source search failed",
    );
    await page.locator(".sa-source-list > button").first().waitFor();
    await page.locator(".sa-source-list > button").first().click();
    await page.locator(".sa-source-detail .hr-original").waitFor();
    assert(
      (await page.locator(".sa-source-detail .hr-original").textContent()) ===
        searchData.results[0].text,
      "Actual original changed",
    );
    await page
      .getByRole("button", { name: "근거 자료 닫기", exact: true })
      .click();
    record(
      "Inline real source search, hash/scope validation and exact original lookup",
      "actual local BFF GETs, no model generation",
    );

    await send(fixture.response);
    await page.locator(".sa-answer-part").first().waitFor();
    assert(
      (await page.locator(".sa-answer-part").first().innerText()).includes(
        fixture.response.paragraphs[0].text,
      ),
      "Retained answer missing",
    );
    await page
      .getByRole("button", { name: "답변과 출처 복사", exact: true })
      .click();
    await page.waitForFunction(() => !!window.__qaCopiedAnswer);
    const copied = await page.evaluate(() => window.__qaCopiedAnswer);
    assert(
      copied.includes(fixture.response.notice) &&
        copied.includes(fixture.response.paragraphs[0].text),
      "Copy dropped answer limitations",
    );
    for (const card of fixture.response.source_conditions ?? [])
      assert(copied.includes(card.quote), "Copy omitted condition original");
    await page.locator(".sa-citations button").first().click();
    await page.locator(".sa-source-detail .hr-original").waitFor();
    const firstCited = fixture.response.sources.find(
      (s) => s.id === fixture.response.paragraphs[0].citations[0].source_id,
    );
    assert(
      (await page.locator(".sa-source-detail .hr-original").textContent()) ===
        firstCited.text,
      "Cited original lookup changed",
    );
    await page
      .getByRole("button", { name: "현재 대화의 질문 목록", exact: true })
      .click();
    await page
      .getByRole("dialog")
      .getByRole("button")
      .filter({ hasText: fixture.question })
      .click();
    record(
      "Retained answer, cited current original, question navigation and full copy content",
      "actual retained answer/current source; clipboard is explicitly mocked",
    );

    const clarify = clone(fixture.response);
    Object.assign(clarify, {
      status: "answered",
      paragraphs: [],
      sources: [],
      source_conditions: [],
      condition_review_required: [],
      provider_calls: [{ phase: "question_understanding" }],
      understanding: {
        status: "needs_clarification",
        intents: [],
        interpreted_as: "",
        employment: "unspecified",
        explicit_conditions: [],
        clarification: "연차 일수와 사용 시기 중 무엇이 궁금하세요?",
        original_question_preserved: true,
        employee_profile_sent: false,
        eligibility_decision: false,
      },
    });
    clarify.missing_information = [clarify.understanding.clarification];
    await send(clarify, "연차가 궁금해요.");
    await page.getByText("질문 확인 필요", { exact: true }).waitFor();
    assert(
      (await page
        .getByText(clarify.understanding.clarification, { exact: true })
        .count()) === 1 &&
        (await page.locator(".sa-answer-part,.sa-citations button").count()) ===
          0,
      "Clarification turned into regulation answer",
    );
    record(
      "Clarification is shown once without generated answer or sources",
      "synthetic clarification transport",
    );
    const withheld = clone(fixture.response);
    withheld.generated_text_withheld = true;
    await send(withheld);
    await page
      .getByText(
        "검사를 통과하지 못한 생성 문장은 표시하지 않았습니다. 확인된 원문과 추가 확인 항목을 살펴보세요.",
        { exact: true },
      )
      .waitFor();
    assert(
      (await page.locator(".sa-answer-part").count()) === 0,
      "Withheld body was displayed",
    );
    const partial = clone(fixture.response);
    partial.partial_verified_text = true;
    await send(partial);
    await page.getByText("일부 답변 · 확인 필요", { exact: true }).waitFor();
    record(
      "Withheld and partial responses retain review status",
      "explicit synthetic transport flags",
    );

    for (const [name, alter] of [
      ["changed original SHA", (d) => (d.sources[0].sha256 = "0".repeat(64))],
      [
        "quote absent from original",
        (d) =>
          (d.paragraphs[0].citations[0].quote =
            "원문에 존재하지 않는 합성 검사 인용입니다."),
      ],
      [
        "changed question condition",
        (d) => (d.understanding.explicit_conditions = ["원질문에 없는 999일"]),
      ],
    ]) {
      const invalid = clone(fixture.response);
      alter(invalid);
      await send(invalid);
      await page.locator(".sa-response-error").waitFor();
      assert(
        (await page.locator(".sa-answer-part,.sa-citations button").count()) ===
          0,
        "Unverified answer rendered: " + name,
      );
      record(name, "tampered retained response");
    }
    await send(fixture.response, fixture.question, 503);
    await page.locator(".sa-response-error").waitFor();
    const before = answerPosts;
    await page
      .getByRole("button", { name: "질문 다시 작성", exact: true })
      .click();
    assert(
      (await page
        .getByRole("textbox", { name: "인사 질문", exact: true })
        .inputValue()) === fixture.question && answerPosts === before,
      "Retry auto-submitted or lost question",
    );
    record(
      "Transport error offers draft recovery without replacement answer",
      "synthetic 503",
    );

    await send(fixture.response);
    await page.locator(".sa-answer-part").first().waitFor();
    for (const width of [1920, 1440, 1024, 768, 390, 360]) {
      await page.setViewportSize({ width, height: width < 500 ? 844 : 1040 });
      await page.evaluate(
        () =>
          new Promise((resolve) =>
            requestAnimationFrame(() => requestAnimationFrame(resolve)),
          ),
      );
      const dimension = await page.evaluate(
        () => document.documentElement.scrollWidth,
      );
      assert(dimension <= width + 1, "Chat overflow at " + width);
      widths.push({ width, documentWidth: dimension });
      if (width === 390) {
        await page
          .getByRole("button", { name: "근거 자료", exact: true })
          .click();
        await page
          .getByRole("dialog", { name: "근거 자료", exact: true })
          .waitFor();
        await page.keyboard.press("Escape");
      }
    }
    record(
      "Six responsive widths and mobile evidence dialog",
      "retained response UI",
    );
    await reset();
    for (const width of [1440, 390]) {
      await page.setViewportSize({ width, height: width < 500 ? 844 : 1040 });
      await page.evaluate(() => {
        document.activeElement?.blur();
        window.scrollTo(0, 0);
      });
      await page.mouse.move(0, 0);
      await page.screenshot({
        path: "output/playwright/hr-saas-assistant-empty-" + width + ".png",
        fullPage: true,
      });
    }
    await page.setViewportSize({ width: 1440, height: 1040 });
    await page.goto(base + "/hr/assistant-previous");
    await page.locator(".hr-assistant").waitFor();
    assert(
      (await page.locator(".sa-assistant").count()) === 0,
      "Previous chat replaced",
    );
    record(
      "Previous assistant preserved in its original layout",
      "actual old route",
    );
    assert(
      !requests.some((r) => r.path === "/api/benefits/config" || r.auth),
      "Cloud config or browser authorization request",
    );
    assert(!errors.length, "Browser script errors: " + errors.join(";"));
    return {
      status: "PASSED",
      checkedAt: new Date().toISOString(),
      checks,
      widths,
      interceptedAnswerRequests: answerPosts,
      newModelGenerations: 0,
      browserErrors: errors,
      scope:
        "Source/answer UI and contract preservation; synthetic fixtures/clipboard are identified; not answer-quality evaluation",
    };
  } catch (error) {
    return {
      status: "FAILED",
      error: error.message,
      checks,
      widths,
      browserErrors: errors,
      interceptedAnswerRequests: answerPosts,
    };
  } finally {
    await page.unroute(route);
  }
}

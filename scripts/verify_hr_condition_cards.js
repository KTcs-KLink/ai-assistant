// Inject only the selected preserved responses with prepare_hr_condition_check.py.
// These are labelled replays, not fresh model calls or an answer-quality score.
async function verifyHrConditionCards(page) {
  const fixtures = /* LOCAL_REPLAY_FIXTURES */ [];
  const base = "http://127.0.0.1:8825",
    answerUrl = base + "/api/benefits/hr/answer";
  const checks = [],
    requests = [],
    errors = [];
  page.setDefaultTimeout(15000);
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.pathname.startsWith("/api/benefits")) requests.push(url.pathname);
  });
  const assert = (value, message) => {
    if (!value) throw Error(message);
  };
  const observe = async () => {
    await page.evaluate(
      () =>
        new Promise((resolve) =>
          requestAnimationFrame(() => requestAnimationFrame(resolve)),
        ),
    );
    return page.locator("body").ariaSnapshot();
  };
  async function render(data, question) {
    await page.getByRole("button", { name: "새 대화", exact: true }).click();
    await page.route(answerUrl, (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(data),
      }),
    );
    await page
      .getByRole("textbox", { name: "서버 인사 질문", exact: true })
      .fill(question);
    await page
      .getByRole("button", { name: "서버에 인사 질문 보내기", exact: true })
      .click();
    await page
      .getByRole("button", { name: "서버에 인사 질문 보내기", exact: true })
      .waitFor();
    await page.waitForFunction(() =>
      document
        .querySelector('button[aria-label="서버에 인사 질문 보내기"]')
        ?.textContent?.includes("질문 보내기"),
    );
    await page.unroute(answerUrl);
    await observe();
  }
  try {
    assert(
      fixtures.length === 3,
      "Prepare the three local replay fixtures first",
    );
    await page.setViewportSize({ width: 1440, height: 1040 });
    await page.goto(base + "/hr/assistant");
    await page.getByRole("heading", { level: 1 }).waitFor();
    await observe();
    const start = page.getByRole("button", {
      name: "예시 직원으로 인사 기능 시작",
      exact: true,
    });
    if (await start.isVisible()) {
      await start.click();
      await page.locator('.hr-app[aria-busy="false"]').waitFor();
      await page
        .getByRole("navigation", { name: "인사 포털 메뉴" })
        .getByRole("link", { name: "AI 업무 도우미", exact: true })
        .click();
    }
    await observe();
    for (const fixture of fixtures) {
      await render(fixture.response, fixture.question);
      await page
        .getByRole("heading", {
          name: "함께 확인할 조건·예외 원문",
          exact: true,
        })
        .waitFor();
      const quotes = page.locator(".hr-condition-quote");
      assert(
        (await quotes.count()) === fixture.response.source_conditions.length,
        "Card count mismatch " + fixture.case_id,
      );
      for (let i = 0; i < (await quotes.count()); i++)
        assert(
          (await quotes.nth(i).textContent()) ===
            fixture.response.source_conditions[i].quote,
          "Source paragraph shortened or altered",
        );
      assert(
        (await page.locator(".hr-source-conditions details").count()) === 0,
        "Conditions are hidden behind disclosure",
      );
      assert(
        await page
          .locator(".hr-source-conditions")
          .evaluate((el) => !!el.closest(".p-message.assistant")),
        "Conditions not immediately in the answer",
      );
      await page
        .getByText(
          "다른 조문의 필수 조건까지 모두 찾았거나 실제 회사 자격을 확인했다는 뜻은 아닙니다.",
          { exact: false },
        )
        .waitFor();
      await page
        .getByText("보존 응답 재생 · 새 모델 호출 아님", { exact: true })
        .waitFor();
      if (fixture.response.partial_verified_text) {
        await page
          .getByText("인용 검사를 통과하지 못한 설명은 제외하고", {
            exact: false,
          })
          .waitFor();
        assert(
          await page.getByText("추가 확인 필요", { exact: true }).isVisible(),
          "Partial answer promoted",
        );
      }
      checks.push({
        name: fixture.case_id,
        mode: "preserved actual response replay via interception",
        cards: await quotes.count(),
        fullTextExact: true,
        partial: !!fixture.response.partial_verified_text,
        passed: true,
      });
    }
    const normal = structuredClone(fixtures[0].response);
    for (const [name, mutate] of [
      [
        "wrong quote hash",
        (value) => (value.source_conditions[0].quote_sha256 = "0".repeat(64)),
      ],
      ["wrong source offset", (value) => value.source_conditions[0].start++],
      [
        "unsupported all-article coverage",
        (value) =>
          (value.condition_coverage = "ALL_REQUIRED_ARTICLES_APPROVED"),
      ],
    ]) {
      const value = structuredClone(normal);
      mutate(value);
      await render(value, "검사 전용 원문 연결 오류 확인");
      await page
        .getByText("답변을 확인하지 못했어요", { exact: true })
        .waitFor();
      assert(
        (await page.locator(".hr-answer-part,.hr-condition-quote").count()) ===
          0,
        "Invalid answer/card displayed",
      );
      checks.push({ name, mode: "tampered replay response", passed: true });
    }
    const quoted = "① 합성 문자열 조건을 그대로 보존합니다.\n",
      full = "🧭" + quoted + "② 별도 합성 항입니다.";
    const hashes = await page.evaluate(
      async ({ full, quoted }) => {
        const sha = async (text) =>
          Array.from(
            new Uint8Array(
              await crypto.subtle.digest(
                "SHA-256",
                new TextEncoder().encode(text),
              ),
            ),
          )
            .map((b) => b.toString(16).padStart(2, "0"))
            .join("");
        return { source: await sha(full), quote: await sha(quoted) };
      },
      { full, quoted },
    );
    const unicode = {
      missing_information: [],
      company: "TEST",
      ktcs_applicable: false,
      human_approved: false,
      employee_data_sent: false,
      status: "answered",
      paragraphs: [
        {
          text: "합성 문자열의 문자 위치를 검사합니다.",
          citations: [{ source_id: "TEST-UNICODE", quote: quoted }],
        },
      ],
      sources: [
        {
          id: "TEST-UNICODE",
          title: "합성 문자열 검사",
          section: "시험 전용",
          text: full,
          sha256: hashes.source,
          version: "test",
          company: "TEST",
          employee_scope: "실제 규정 아님",
          human_approved: false,
          ktcs_applicable: false,
        },
      ],
      notice: "합성 문자열 검사이며 회사 규정이 아닙니다.",
      source_conditions: [
        {
          source_id: "TEST-UNICODE",
          title: "합성 문자열 검사",
          section: "시험 전용",
          quote: quoted,
          start: 1,
          end: 1 + Array.from(quoted).length,
          source_sha256: hashes.source,
          quote_sha256: hashes.quote,
          kind: "ORIGINAL_SOURCE_PARAGRAPH_NOT_GENERATED",
          human_approved: false,
        },
      ],
      condition_coverage: "CITED_PARAGRAPHS_ONLY_NOT_ALL_REQUIRED_ARTICLES",
      condition_review_required: [],
      partial_verified_text: false,
      validation:
        "AUTOMATIC_SOURCE_COMPARISON_ID_QUOTE_NUMBER_CHECKS_NOT_HUMAN_APPROVAL",
    };
    await render(unicode, "합성 문자열의 유니코드 위치 검사");
    await page.locator(".hr-condition-quote").waitFor();
    assert(
      (await page.locator(".hr-condition-quote").textContent()) === quoted,
      "Python Unicode offsets interpreted as UTF-16",
    );
    checks.push({
      name: "Unicode code-point offsets and UTF-8 hashes",
      mode: "explicit synthetic TEST source",
      passed: true,
    });
    await render(fixtures[0].response, fixtures[0].question);
    await page.locator(".hr-condition-quote").first().waitFor();
    const viewports = [];
    for (const width of [1440, 768, 390, 360]) {
      await page.setViewportSize({ width, height: width <= 390 ? 844 : 1040 });
      await page.evaluate(() => {
        const chat = document.querySelector(".p-chat-messages"),
          cards = document.querySelector(".hr-source-conditions");
        window.scrollTo(0, 0);
        if (chat && cards)
          chat.scrollTop +=
            cards.getBoundingClientRect().top -
            chat.getBoundingClientRect().top;
      });
      const sizes = await page.evaluate(() => ({
        width: innerWidth,
        document: document.documentElement.scrollWidth,
      }));
      assert(
        sizes.document <= sizes.width + 1,
        "Condition cards cause horizontal overflow",
      );
      for (const quote of await page.locator(".hr-condition-quote").all())
        assert(
          await quote.evaluate((el) => el.scrollHeight <= el.clientHeight + 1),
          "Condition paragraph vertically truncated",
        );
      viewports.push(sizes);
      if (width === 1440 || width === 390)
        await page.screenshot({
          path: "output/playwright/hr-condition-cards-replay-" + width + ".png",
          fullPage: width === 1440,
        });
    }
    assert(
      !requests.some((path) => path === "/api/benefits/config"),
      "Cloud status endpoint was automatically requested",
    );
    assert(!errors.length, "Browser errors: " + errors.join("; "));
    await page.setViewportSize({ width: 1440, height: 1040 });
    return {
      status: "PASSED",
      checks,
      viewports,
      cloudStatusRequests: 0,
      paidModelCalls: 0,
      replay: true,
      sourceTextUnchanged: true,
      errors,
      scope:
        "Bounded UI integrity/replay/failure checks, not a new retrieval or answer-quality evaluation",
    };
  } catch (error) {
    return { status: "FAILED", error: error.message, checks, errors };
  }
}

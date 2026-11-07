// Two actual UI/BFF requests to the delegated semantic HR service.
// This deliberately invokes the configured model; retain stdout in ignored output/playwright.
async function verifyHrIntentPortal(page) {
  const base = "http://127.0.0.1:8825";
  const questions = [
    "통상근무자의 휴게시간을 업무 사정으로 바꿀 수 있나요?",
    "일 때문에 점심 쉬는 시간을 다른 때로 옮겨도 되나요?",
  ];
  const records = [],
    errors = [],
    requests = [],
    viewports = [];
  const check = (condition, message) => {
    if (!condition) throw Error(message);
  };
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.pathname.startsWith("/api/benefits"))
      requests.push({
        path: url.pathname,
        method: request.method(),
        authorization: !!request.headers().authorization,
        bodyKeys: request.postData()
          ? Object.keys(JSON.parse(request.postData()))
          : [],
      });
  });
  page.setDefaultTimeout(20000);
  try {
    await page.setViewportSize({ width: 1440, height: 1040 });
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
    await page.locator(".hr-retrieval-connection.configured").waitFor();
    check(
      (await page.locator(".hr-retrieval-connection").innerText()).includes(
        "질문 의미 분석",
      ),
      "Semantic capability not shown",
    );
    for (const question of questions) {
      await page
        .getByRole("textbox", { name: "서버 인사 질문", exact: true })
        .fill(question);
      const pending = page.waitForResponse(
        (r) =>
          r.url().endsWith("/api/benefits/hr/answer") &&
          r.request().method() === "POST",
        { timeout: 550000 },
      );
      await page
        .getByRole("button", { name: "서버에 인사 질문 보내기", exact: true })
        .click();
      const response = await pending,
        data = await response.json();
      records.push({ question, httpStatus: response.status(), response: data });
      check(response.status() === 200, "BFF status " + response.status());
      check(
        data.understanding?.status === "ready",
        "Question not ready: " + JSON.stringify(data.understanding),
      );
      check(
        data.understanding.intents.includes("work_break"),
        "Work-break intent missing",
      );
      check(
        data.understanding.original_question_preserved === true &&
          data.understanding.explicit_conditions.every((c) =>
            question.includes(c),
          ),
        "Original conditions changed",
      );
      check(
        data.provider_calls?.map((c) => c.phase).join(",") ===
          "question_understanding,draft,source_comparison",
        "Three-phase path missing",
      );
      check(
        data.paragraphs.length > 0 && !data.generated_text_withheld,
        "Actual text withheld; inspect retained response",
      );
      check(
        data.retrieval?.method === "hr_bge_m3_hybrid",
        "Hybrid path missing",
      );
      check(
        data.quote_method ===
          "APPLICATION_RECONSTRUCTED_ORIGINAL_SPANS_NO_GENERATED_QUOTES",
        "Quote provenance missing",
      );
      check(
        data.company === "KEPCO" &&
          data.ktcs_applicable === false &&
          data.human_approved === false &&
          data.employee_data_sent === false,
        "Scope changed",
      );
      const conversation = page.locator(".hr-conversation").last();
      await conversation.locator(".hr-answer-part").first().waitFor();
      check(
        (await conversation
          .locator(".hr-question-understanding")
          .innerText()) ===
          "질문을 이렇게 이해했어요: " + data.understanding.interpreted_as,
        "Meaning label mismatch",
      );
      for (const paragraph of data.paragraphs)
        for (const citation of paragraph.citations) {
          const source = data.sources.find((s) => s.id === citation.source_id);
          check(
            source?.text.includes(citation.quote),
            "Quote absent from original",
          );
        }
      for (const card of data.source_conditions ?? []) {
        const source = data.sources.find((s) => s.id === card.source_id);
        check(
          source &&
            Array.from(source.text).slice(card.start, card.end).join("") ===
              card.quote,
          "Condition offset mismatch",
        );
      }
      await conversation.locator(".hr-retrieval-trace summary").click();
      const originals = conversation.locator(".hr-retrieval-trace blockquote");
      check(
        (await originals.count()) === data.sources.length,
        "Original list missing",
      );
      for (let i = 0; i < data.sources.length; i++)
        check(
          (await originals.nth(i).textContent()) === data.sources[i].text,
          "Original text changed",
        );
      await conversation.locator(".hr-retrieval-trace summary").click();
    }
    const cited = (data) =>
      new Set(
        data.paragraphs.flatMap((p) => p.citations.map((c) => c.source_id)),
      );
    const commonIds = [...cited(records[0].response)].filter((id) =>
      cited(records[1].response).has(id),
    );
    check(commonIds.length > 0, "Paraphrases have no common cited source");
    const commonSources = commonIds.map((id) => {
      const first = records[0].response.sources.find((s) => s.id === id);
      const second = records[1].response.sources.find((s) => s.id === id);
      check(
        first.sha256 === second.sha256 && first.text === second.text,
        "Common source changed",
      );
      return {
        id,
        title: first.title,
        section: first.section,
        sha256: first.sha256,
      };
    });
    for (const width of [1440, 768, 390, 360]) {
      await page.setViewportSize({ width, height: width < 500 ? 844 : 1040 });
      await page.evaluate(() => {
        document.activeElement?.blur();
        window.scrollTo(0, 0);
        const chat = document.querySelector(".p-chat-messages");
        chat.style.scrollBehavior = "auto";
        chat.scrollTop = 0;
      });
      const documentWidth = await page.evaluate(
        () => document.documentElement.scrollWidth,
      );
      check(documentWidth <= width + 1, "Horizontal overflow at " + width);
      viewports.push({ width, documentWidth });
      if ([1440, 390].includes(width))
        await page.screenshot({
          path: "output/playwright/hr-intent-portal-" + width + ".png",
          fullPage: true,
        });
    }
    check(
      !requests.some(
        (r) =>
          r.path === "/api/benefits/config" ||
          r.path.endsWith("/retrieval/status"),
      ),
      "Cloud/unsupported status requested",
    );
    check(
      !requests.some((r) => r.authorization),
      "Authorization header in browser",
    );
    check(
      requests.filter((r) => r.path.endsWith("/hr/answer")).length === 2,
      "Unexpected answer requests",
    );
    check(
      requests
        .filter((r) => r.path.endsWith("/hr/answer"))
        .every((r) => r.bodyKeys.join(",") === "question"),
      "Profile sent with question",
    );
    check(!errors.length, "Browser errors: " + errors.join(";"));
    return {
      status: "PASSED",
      checkedAt: new Date().toISOString(),
      upstream: "http://127.0.0.1:8844",
      actualAnswerRequests: records.length,
      providerGenerationCalls: records.reduce(
        (n, r) => n + r.response.provider_calls.length,
        0,
      ),
      commonSources,
      viewports,
      pageErrors: errors,
      cloudStatusRequests: 0,
      records,
      scope:
        "Two actual paraphrase UI/source checks; conclusion comparison requires reading retained text, not a benchmark or independent approval",
    };
  } catch (error) {
    return {
      status: "FAILED",
      error: error.message,
      records,
      pageErrors: errors,
      requests,
    };
  }
}

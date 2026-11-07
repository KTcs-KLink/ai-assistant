// One real UI/BFF question to the delegated 8842 service. No cloud-store probe.
async function verifyHrCloseoutPortal(page) {
  const base = "http://127.0.0.1:8825";
  const question =
    "연간 질병휴가가 7일째일 때 필요한 증빙과 동일 사유로 다시 쉬는 경우의 예외를 알려주세요.";
  const errors = [],
    requests = [];
  let received = null;
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.pathname.startsWith("/api/benefits"))
      requests.push({
        path: url.pathname,
        method: request.method(),
        auth: !!request.headers().authorization,
        bodyKeys: request.postData()
          ? Object.keys(JSON.parse(request.postData()))
          : [],
      });
  });
  const check = (condition, message) => {
    if (!condition) throw Error(message);
  };
  try {
    page.setDefaultTimeout(20000);
    await page.setViewportSize({ width: 1440, height: 1040 });
    await page.goto(base + "/hr");
    await page.getByRole("heading", { level: 1 }).waitFor();
    await page.locator("body").ariaSnapshot();
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
    await page.locator("body").ariaSnapshot();
    await page
      .getByRole("textbox", { name: "서버 인사 질문", exact: true })
      .fill(question);
    const pending = page.waitForResponse(
      (r) =>
        r.url().endsWith("/api/benefits/hr/answer") &&
        r.request().method() === "POST",
      { timeout: 385000 },
    );
    await page
      .getByRole("button", { name: "서버에 인사 질문 보내기", exact: true })
      .click();
    const response = await pending,
      data = await response.json();
    received = data;
    check(response.status() === 200, "BFF returned " + response.status());
    check(
      data.retrieval?.method === "hr_bge_m3_hybrid",
      "Latest hybrid path missing",
    );
    check(
      data.quote_method ===
        "APPLICATION_RECONSTRUCTED_ORIGINAL_SPANS_NO_GENERATED_QUOTES",
      "Application-restored quote provenance missing",
    );
    check(
      data.paragraphs.length > 0 && !data.generated_text_withheld,
      "Actual text withheld; inspect retained response",
    );
    check(
      data.company === "KEPCO" &&
        data.ktcs_applicable === false &&
        data.human_approved === false &&
        data.employee_data_sent === false,
      "Scope boundary changed",
    );
    await page.locator(".hr-answer-part").first().waitFor();
    await page.locator(".hr-quote-method").waitFor();
    for (const paragraph of data.paragraphs)
      for (const citation of paragraph.citations) {
        const source = data.sources.find((s) => s.id === citation.source_id);
        check(
          source && source.text.includes(citation.quote),
          "Citation text not in actual original",
        );
      }
    for (const card of data.source_conditions) {
      const source = data.sources.find((s) => s.id === card.source_id);
      check(
        source &&
          Array.from(source.text).slice(card.start, card.end).join("") ===
            card.quote,
        "Condition original offset mismatch",
      );
    }
    await page.locator(".hr-retrieval-trace summary").click();
    const originals = page.locator(".hr-retrieval-trace blockquote");
    check(
      (await originals.count()) === data.sources.length,
      "Original source cards missing",
    );
    for (let i = 0; i < data.sources.length; i++)
      check(
        (await originals.nth(i).textContent()) === data.sources[i].text,
        "Original text changed/truncated",
      );
    await page.locator(".hr-retrieval-trace summary").click();
    const viewports = [];
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
      check(documentWidth <= width + 1, "Overflow at " + width);
      viewports.push({ width, documentWidth });
      if (width === 1440 || width === 390)
        await page.screenshot({
          path: "output/playwright/hr-closeout-portal-" + width + ".png",
          fullPage: true,
        });
    }
    check(
      !requests.some(
        (r) =>
          r.path === "/api/benefits/config" ||
          r.path.endsWith("/retrieval/status"),
      ),
      "Unsupported/cloud status endpoint requested",
    );
    check(
      !requests.some((r) => r.auth),
      "Browser authorization header present",
    );
    check(
      requests
        .filter((r) => r.path.endsWith("/hr/answer"))
        .every((r) => r.bodyKeys.join(",") === "question"),
      "Profile attached to question",
    );
    check(!errors.length, "Browser errors " + errors.join(";"));
    return {
      status: "PASSED",
      checkedAt: new Date().toISOString(),
      upstream: "http://127.0.0.1:8842",
      question,
      httpStatus: response.status(),
      answerStatus: data.status,
      paragraphCount: data.paragraphs.length,
      sourceCount: data.sources.length,
      conditionCards: data.source_conditions.length,
      quoteMethod: data.quote_method,
      retrievalMethod: data.retrieval.method,
      actualAnswerRequests: 1,
      providerGenerationCalls: data.provider_calls?.length ?? 0,
      company: data.company,
      ktcsApplicable: data.ktcs_applicable,
      humanApproved: data.human_approved,
      employeeDataSent: data.employee_data_sent,
      exactOriginalsAndConditions: true,
      cloudStatusRequests: 0,
      unsupportedStatusRequests: 0,
      pageErrors: errors,
      viewports,
      response: data,
      scope:
        "One latest-service UI/source/quote connection check; not a new retrieval benchmark or independent semantic approval",
    };
  } catch (error) {
    return {
      status: "FAILED",
      error: error.message,
      pageErrors: errors,
      response: received,
    };
  }
}

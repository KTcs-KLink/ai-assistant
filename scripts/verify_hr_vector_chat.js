// One actual browser/BFF question; up to two configured-model generations.
async function verifyHrVectorChat(page) {
  const base = "http://127.0.0.1:8825",
    question = "병가 누계가 7일이 되면 어떤 증빙이 필요한가요?";
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
        authorization: !!request.headers().authorization,
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
    await page
      .locator(".hr-retrieval-connection.ready")
      .waitFor({ timeout: 60000 });
    await page.locator("body").ariaSnapshot();
    const pending = page.waitForResponse(
      (r) =>
        r.url().endsWith("/api/benefits/hr/answer") &&
        r.request().method() === "POST",
      { timeout: 385000 },
    );
    await page
      .getByRole("textbox", { name: "서버 인사 질문", exact: true })
      .fill(question);
    await page
      .getByRole("button", { name: "서버에 인사 질문 보내기", exact: true })
      .click();
    const response = await pending;
    const data = await response.json();
    received = data;
    check(
      response.status() === 200,
      "Actual BFF returned " + response.status(),
    );
    const trace = data.retrieval;
    check(
      trace?.method === "local_bge_m3_dense" && trace.status === "RETRIEVED",
      "Not actual local dense retrieval",
    );
    check(
      trace.embedding?.computed === true &&
        trace.embedding.cached === false &&
        trace.embedding.dimension === 1024,
      "Query embedding not freshly computed",
    );
    check(
      trace.embedding.model === "BAAI/bge-m3" &&
        trace.lexical_fallback === false,
      "Embedding identity/fallback changed",
    );
    check(
      trace.index.source_count === 449 &&
        trace.index.window_count === 456 &&
        trace.index.read_only === true,
      "Allowed source scope changed",
    );
    check(
      trace.index.numeric_compatibility.minimum_cosine >= 0.9999,
      "Numeric compatibility not verified",
    );
    check(
      trace.matches.length === 5 && trace.source_unit_ids.length === 5,
      "Actual chunk/source handoff missing",
    );
    check(
      data.sources[0].section.includes("질병휴가"),
      "Selected question did not retrieve the related source first",
    );
    check(
      data.company === "KEPCO" &&
        !data.ktcs_applicable &&
        !data.human_approved &&
        !data.employee_data_sent,
      "Company/employee boundary changed",
    );
    check(
      data.paragraphs.length > 0 && !data.generated_text_withheld,
      "Actual text was withheld; inspect received result",
    );
    check(
      data.provider_calls?.map((call) => call.phase).join(",") ===
        "draft,source_comparison",
      "Configured LLM phases missing",
    );
    await page.locator(".hr-answer-part").first().waitFor();
    await page.locator(".hr-retrieval-trace summary").click();
    const displayed = page.locator(".hr-retrieval-trace blockquote");
    check(
      (await displayed.count()) === trace.matches.length,
      "Retrieved chunk cards missing",
    );
    for (const [index, chunk] of trace.matches.entries()) {
      const source = data.sources.find((s) => s.id === chunk.source_id);
      check(
        Array.from(source.text).slice(chunk.start, chunk.end).join("") ===
          chunk.text,
        "Actual source offset mismatch",
      );
      check(
        (await displayed.nth(index).textContent()) === chunk.text,
        "Chunk text changed/truncated in UI",
      );
    }
    await page.locator(".hr-retrieval-trace summary").click();
    await page.locator(".hr-source-conditions").waitFor();
    const viewports = [];
    for (const width of [1440, 768, 390, 360]) {
      await page.setViewportSize({ width, height: width < 500 ? 844 : 1040 });
      await page.evaluate(
        () =>
          new Promise((resolve) =>
            requestAnimationFrame(() => requestAnimationFrame(resolve)),
          ),
      );
      const documentWidth = await page.evaluate(
        () => document.documentElement.scrollWidth,
      );
      check(documentWidth <= width + 1, "Horizontal overflow at " + width);
      viewports.push({ width, documentWidth });
      if (width === 1440 || width === 390)
        await page.screenshot({
          path: "output/playwright/hr-vector-live-" + width + ".png",
          fullPage: true,
        });
    }
    check(
      !requests.some((r) => r.path === "/api/benefits/config"),
      "Cloud store was probed",
    );
    check(
      !requests.some((r) => r.authorization),
      "Browser authorization header present",
    );
    check(
      requests
        .filter((r) => r.path.endsWith("/hr/answer"))
        .every((r) => r.bodyKeys.join(",") === "question"),
      "Employee attributes attached to question",
    );
    check(!errors.length, "Browser errors: " + errors.join("; "));
    return {
      status: "PASSED",
      checkedAt: new Date().toISOString(),
      httpStatus: response.status(),
      question,
      actualAnswerRequests: 1,
      providerGenerationCalls: data.provider_calls.length,
      answerStatus: data.status,
      paragraphCount: data.paragraphs.length,
      conditionCards: data.source_conditions.length,
      retrievalMethod: trace.method,
      embedding: trace.embedding,
      index: trace.index,
      matchedChunkIds: trace.matches.map((c) => c.chunk_id),
      sourceIds: trace.source_unit_ids,
      sourceSections: data.sources.map((s) => s.section),
      fullChunkTextDisplayed: true,
      company: data.company,
      ktcsApplicable: data.ktcs_applicable,
      humanApproved: data.human_approved,
      employeeDataSent: data.employee_data_sent,
      cloudStatusRequests: 0,
      pageErrors: errors,
      viewports,
      response: data,
      scope:
        "One real query embedding/local-chunk/configured-LLM/UI connection check; not a retrieval benchmark, semantic accuracy score or company approval",
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

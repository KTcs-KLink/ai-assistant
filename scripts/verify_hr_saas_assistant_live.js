// One actual answer request through the new SaaS assistant. Model calls occur.
async function verifySaasAssistantLive(page) {
  const base = "http://127.0.0.1:8825",
    question = "통상근무자의 휴게시간을 업무 사정으로 바꿀 수 있나요?";
  const errors = [],
    requests = [],
    widths = [];
  let received = null;
  const assert = (value, message) => {
    if (!value) throw Error(message);
  };
  page.setDefaultTimeout(20000);
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("request", (request) => {
    const path = new URL(request.url()).pathname;
    if (path.startsWith("/api/benefits"))
      requests.push({
        path,
        method: request.method(),
        auth: !!request.headers().authorization,
        bodyKeys: request.postData()
          ? Object.keys(JSON.parse(request.postData()))
          : [],
      });
  });
  try {
    await page.setViewportSize({ width: 1440, height: 1040 });
    await page.goto(base + "/hr/assistant");
    await page.getByRole("heading", { level: 1 }).waitFor();
    const login = page.getByRole("button", {
      name: "예시 직원으로 인사 기능 시작",
      exact: true,
    });
    if (await login.isVisible()) {
      await login.click();
      await page.locator(".hr-saas").waitFor();
      await page.goto(base + "/hr/assistant");
    }
    await page.locator(".sa-assistant").waitFor();
    await page.locator("body").ariaSnapshot();
    const closeNotice = page.getByRole("button", {
      name: "안내 닫기",
      exact: true,
    });
    if (await closeNotice.isVisible()) await closeNotice.click();
    await page
      .getByRole("textbox", { name: "인사 질문", exact: true })
      .fill(question);
    const pending = page.waitForResponse(
      (r) =>
        r.url().endsWith("/api/benefits/hr/answer") &&
        r.request().method() === "POST",
      { timeout: 550000 },
    );
    await page
      .getByRole("button", { name: "인사 질문 전송", exact: true })
      .click();
    const response = await pending,
      data = await response.json();
    received = data;
    assert(response.status() === 200, "Answer HTTP " + response.status());
    assert(
      data.paragraphs?.length > 0 && !data.generated_text_withheld,
      "Actual answer withheld; inspect retained response",
    );
    assert(
      data.retrieval?.method === "hr_bge_m3_hybrid" &&
        data.company === "KEPCO" &&
        data.ktcs_applicable === false &&
        data.human_approved === false &&
        data.employee_data_sent === false,
      "Source/company boundary changed",
    );
    assert(
      data.quote_method ===
        "APPLICATION_RECONSTRUCTED_ORIGINAL_SPANS_NO_GENERATED_QUOTES",
      "Quote method changed",
    );
    await page.locator(".sa-answer-part").first().waitFor();
    for (let index = 0; index < data.paragraphs.length; index++) {
      assert(
        (await page.locator(".sa-answer-part > p").nth(index).textContent()) ===
          data.paragraphs[index].text,
        "Actual paragraph changed",
      );
      for (const citation of data.paragraphs[index].citations)
        assert(
          data.sources
            .find((source) => source.id === citation.source_id)
            ?.text.includes(citation.quote),
          "Citation missing from original",
        );
    }
    await page.locator(".sa-citations button").first().click();
    await page.locator(".sa-source-detail .hr-original").waitFor();
    const cited = data.sources.find(
      (source) => source.id === data.paragraphs[0].citations[0].source_id,
    );
    assert(
      (await page.locator(".sa-source-detail .hr-original").textContent()) ===
        cited.text,
      "Current original lookup mismatch",
    );
    await page.evaluate(() => {
      document.activeElement?.blur();
      window.scrollTo(0, 0);
      const node = document.querySelector(".sa-transcript");
      node.scrollTop = 0;
    });
    await page.screenshot({
      path: "output/playwright/hr-saas-assistant-live-1440.png",
      fullPage: true,
    });
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
      assert(documentWidth <= width + 1, "Actual-answer overflow at " + width);
      widths.push({ width, documentWidth });
      if (width === 390) {
        await page.evaluate(() => {
          document.activeElement?.blur();
          window.scrollTo(0, 0);
          document.querySelector(".sa-transcript").scrollTop = 0;
        });
        await page.mouse.move(0, 0);
        await page.screenshot({
          path: "output/playwright/hr-saas-assistant-live-390.png",
          fullPage: true,
        });
        await page.locator(".sa-citations button").first().click();
        await page
          .getByRole("dialog", { name: "근거 자료", exact: true })
          .waitFor();
        await page.locator(".sa-source-detail .hr-original").waitFor();
        assert(
          (await page
            .locator(".sa-source-detail .hr-original")
            .textContent()) === cited.text,
          "Mobile original changed",
        );
        await page.screenshot({
          path: "output/playwright/hr-saas-assistant-source-390.png",
          fullPage: true,
        });
        await page.keyboard.press("Escape");
      }
    }
    const answerRequests = requests.filter((r) =>
      r.path.endsWith("/hr/answer"),
    );
    assert(
      answerRequests.length === 1 &&
        answerRequests[0].bodyKeys.join(",") === "question",
      "Unexpected request count or profile included",
    );
    assert(
      !requests.some((r) => r.auth || r.path === "/api/benefits/config"),
      "Browser auth or cloud config probe",
    );
    assert(!errors.length, "Browser errors " + errors.join(";"));
    return {
      status: "PASSED",
      checkedAt: new Date().toISOString(),
      question,
      actualAnswerRequests: answerRequests.length,
      providerGenerationCalls: data.provider_calls?.length ?? 0,
      providerPhases: data.provider_calls?.map((call) => call.phase),
      answerStatus: data.status,
      paragraphCount: data.paragraphs.length,
      sourceCount: data.sources.length,
      exactOriginalLookup: true,
      requestBodyKeys: answerRequests[0].bodyKeys,
      widths,
      pageErrors: errors,
      response: data,
      scope:
        "One real UI/source/answer connection check; not retrieval benchmarking or independent semantic approval",
    };
  } catch (error) {
    return {
      status: "FAILED",
      error: error.message,
      pageErrors: errors,
      response: received,
      requests,
    };
  }
}

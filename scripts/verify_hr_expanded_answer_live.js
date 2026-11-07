// One actual UI question on expanded 8846 through the 8825 proxy.
// This deliberately makes a real model request, separate from scope fixtures.
async function verifyExpandedAnswerLive(page) {
  const base = "http://127.0.0.1:8825";
  const question = "월급은 매달 며칠 들어오나요?";
  const requests = [],
    errors = [],
    widths = [];
  let received = null;
  const assert = (value, message) => {
    if (!value) throw Error(message);
  };
  page.setDefaultTimeout(20000);
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
    const notice = page.getByRole("button", { name: "안내 닫기", exact: true });
    if (await notice.isVisible()) await notice.click();
    await page
      .getByRole("textbox", { name: "인사 질문", exact: true })
      .fill(question);
    const pending = page.waitForResponse(
      (response) =>
        response.url().endsWith("/hr/answer") &&
        response.request().method() === "POST",
      { timeout: 550000 },
    );
    await page
      .getByRole("button", { name: "인사 질문 전송", exact: true })
      .click();
    const response = await pending,
      data = await response.json();
    received = data;
    assert(
      response.status() === 200 &&
        data.paragraphs?.length > 0 &&
        !data.generated_text_withheld,
      "Actual answer unavailable or withheld",
    );
    assert(
      data.retrieval?.method === "hr_bge_m3_hybrid" &&
        data.retrieval?.source_scope === "expanded" &&
        data.retrieval?.source_count === 528 &&
        data.retrieval?.review_only_count === 3334,
      "Expanded retrieval not used",
    );
    assert(
      data.company === "KEPCO" &&
        data.ktcs_applicable === false &&
        data.human_approved === false &&
        data.employee_data_sent === false,
      "Company/approval boundary changed",
    );
    assert(
      data.sources.every(
        (source) =>
          source.answer_eligible === true &&
          source.review_only === false &&
          source.source_mapping_verified === true,
      ),
      "Review-only source entered generation result",
    );
    assert(
      data.provider_calls?.length > 0,
      "Expected actual model call receipt",
    );
    await page.locator(".sa-answer-part").first().waitFor();
    for (let index = 0; index < data.paragraphs.length; index++) {
      assert(
        (await page.locator(".sa-answer-part > p").nth(index).textContent()) ===
          data.paragraphs[index].text,
        "Rendered answer changed",
      );
      for (const citation of data.paragraphs[index].citations)
        assert(
          data.sources
            .find((source) => source.id === citation.source_id)
            ?.text.includes(citation.quote),
          "Citation does not match original",
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
      "Live original lookup changed",
    );
    await page.evaluate(() => {
      document.activeElement?.blur();
      document.querySelector(".sa-transcript").scrollTop = 0;
    });
    await page.screenshot({
      path: "output/playwright/hr-expanded-answer-1440.png",
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
      assert(documentWidth <= width + 1, "Live answer overflow at " + width);
      widths.push({ width, documentWidth });
      if (width === 390) {
        await page.evaluate(() => {
          document.activeElement?.blur();
          document.querySelector(".sa-transcript").scrollTop = 0;
        });
        await page.mouse.move(0, 0);
        await page.screenshot({
          path: "output/playwright/hr-expanded-answer-390.png",
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
          "Mobile original lookup changed",
        );
        await page.keyboard.press("Escape");
      }
    }
    const answerRequests = requests.filter((request) =>
      request.path.endsWith("/hr/answer"),
    );
    assert(
      answerRequests.length === 1 &&
        answerRequests[0].bodyKeys.join(",") === "question",
      "Repeated request or employee profile sent",
    );
    assert(
      !requests.some(
        (request) => request.auth || request.path === "/api/benefits/config",
      ),
      "Browser credential/cloud probe",
    );
    assert(!errors.length, "Browser errors " + errors.join(";"));
    return {
      status: "PASSED",
      checkedAt: new Date().toISOString(),
      question,
      actualAnswerRequests: 1,
      providerCalls: data.provider_calls.length,
      providerPhases: data.provider_calls.map((call) => call.phase),
      sourceScope: data.retrieval.source_scope,
      answerStatus: data.status,
      paragraphCount: data.paragraphs.length,
      citedSourceIds: data.paragraphs.flatMap((paragraph) =>
        paragraph.citations.map((citation) => citation.source_id),
      ),
      exactOriginalLookup: true,
      requestBodyKeys: answerRequests[0].bodyKeys,
      widths,
      pageErrors: errors,
      response: data,
      scope:
        "One actual expanded-service UI/source/answer connection; not corpus approval, retrieval benchmarking or independent semantic evaluation",
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

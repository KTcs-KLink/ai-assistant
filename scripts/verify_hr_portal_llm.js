// One BFF request with up to two configured-model generation calls. No cloud-store probe.
async function verifyHrPortalModel(page) {
  const base = "http://127.0.0.1:8825";
  let modelRequests = 0;
  let received = null;
  const publicRequests = [];
  page.on("request", (r) => {
    if (new URL(r.url()).pathname === "/api/benefits/config")
      publicRequests.push("config");
  });
  page.setDefaultTimeout(20000);
  try {
    await page.unroute(base + "/api/benefits/hr/answer");
    await page.setViewportSize({ width: 1440, height: 1040 });
    await page.goto(base + "/hr");
    await page.getByRole("heading", { level: 1 }).waitFor();
    await page.locator("body").ariaSnapshot();
    const start = page.getByRole("button", {
      name: "예시 직원으로 인사 기능 시작",
      exact: true,
    });
    if (await start.isVisible()) {
      await start.click();
      await page.locator('.hr-app[aria-busy="false"]').waitFor();
    }
    await page
      .getByRole("navigation", { name: "인사 포털 메뉴" })
      .getByRole("link", { name: "AI 업무 도우미", exact: true })
      .click();
    await page.locator("body").ariaSnapshot();
    await page
      .getByRole("textbox", { name: "서버 인사 질문", exact: true })
      .fill(
        "민원 대응 때문에 점심 휴게시간을 12시가 아닌 시간대로 운영할 수 있나요?",
      );
    const pending = page.waitForResponse(
      (r) =>
        r.url().endsWith("/api/benefits/hr/answer") &&
        r.request().method() === "POST",
      { timeout: 340000 },
    );
    modelRequests++;
    await page
      .getByRole("button", { name: "서버에 인사 질문 보내기", exact: true })
      .click();
    const response = await pending;
    const data = await response.json();
    received = data;
    if (response.status() !== 200)
      return {
        status: "UNAVAILABLE",
        httpStatus: response.status(),
        failureCode: response.headers()["x-klink-rag-failure"] ?? null,
        actualAnswerRequests: modelRequests,
        actualModelCallCompletion: "not established",
        scope: "Actual BFF/provider failure; no substitute generated answer",
      };
    if (
      data.company !== "KEPCO" ||
      data.ktcs_applicable ||
      data.employee_data_sent ||
      data.human_approved
    )
      throw Error("Research/employee boundaries changed");
    await page
      .getByText(
        data.status === "answered"
          ? "원문을 인용한 참고 답변"
          : "추가 확인 필요",
        { exact: true },
      )
      .first()
      .waitFor();
    if (
      data.generated_text_withheld &&
      (await page.locator(".hr-answer-part").count())
    )
      throw Error("Withheld text is visible");
    if (!data.sources.length)
      throw Error("No reference sources returned for the selected question");
    const pendingSource = page.waitForResponse(
      (r) =>
        r.url().includes("/api/benefits/hr/sources/") &&
        r.request().method() === "GET",
    );
    await page.locator(".hr-answer-sources button").first().click();
    const sourceResponse = await pendingSource;
    if (sourceResponse.status() !== 200) throw Error("Source retrieval failed");
    await page.getByText("독립된 사람 승인 전", { exact: true }).waitFor();
    await page.locator(".hr-evidence-panel .hr-original").waitFor();
    if (data.paragraphs.length && !data.source_conditions?.length)
      throw Error(
        "Latest backend did not expose original condition paragraphs",
      );
    if (data.partial_verified_text && data.status !== "needs_review")
      throw Error("Partial text promoted by backend");
    if (publicRequests.length)
      throw Error("Cloud-store status was automatically requested");
    if (data.source_conditions?.length)
      await page
        .getByRole("heading", {
          name: "함께 확인할 조건·예외 원문",
          exact: true,
        })
        .waitFor();
    await page.evaluate(() => {
      window.scrollTo(0, 0);
      const chat = document.querySelector(".p-chat-messages"),
        cards = document.querySelector(".hr-source-conditions");
      if (chat && cards)
        chat.scrollTop +=
          cards.getBoundingClientRect().top - chat.getBoundingClientRect().top;
    });
    await page.screenshot({
      path: "output/playwright/hr-quality-portal-live-desktop.png",
      fullPage: true,
    });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.screenshot({
      path: "output/playwright/hr-quality-portal-live-mobile.png",
      fullPage: true,
    });
    await page.setViewportSize({ width: 1440, height: 1040 });
    return {
      status: "PASSED",
      checkedAt: new Date().toISOString(),
      httpStatus: response.status(),
      answerStatus: data.status,
      paragraphCount: data.paragraphs.length,
      sourceCount: data.sources.length,
      validation: data.validation ?? null,
      generatedTextWithheld: !!data.generated_text_withheld,
      company: data.company,
      ktcsApplicable: data.ktcs_applicable,
      humanApproved: data.human_approved,
      employeeDataSent: data.employee_data_sent,
      actualAnswerRequests: modelRequests,
      configuredModelCalled: !!data.model,
      sourceLookupStatus: sourceResponse.status(),
      desktopAndMobileCaptured: true,
      conditionCards: data.source_conditions?.length ?? 0,
      conditionCoverage: data.condition_coverage ?? null,
      conditionReviewRequired: data.condition_review_required ?? [],
      partialVerifiedText: !!data.partial_verified_text,
      providerGenerationCalls: data.provider_calls?.length ?? 0,
      independentReview: data.semantic_review?.independent ?? false,
      cloudStoreStatusRequests: publicRequests.length,
      response: received,
      scope:
        "One live browser/BFF answer request with up to two configured-model generations and original-source display; not independent answer-quality evaluation or KTcs eligibility approval",
    };
  } catch (error) {
    return {
      status: "FAILED",
      error: error.message,
      actualAnswerRequests: modelRequests,
      response: received,
    };
  }
}

// One actual configured-model request through the connected portal. No credentials in output.
async function verifyHrPortalModel(page) {
  const base = "http://127.0.0.1:8825";
  let modelRequests = 0;
  page.setDefaultTimeout(20000);
  try {
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
      .fill("육아휴직 기간은 어떤 조문에서 확인하나요?");
    const pending = page.waitForResponse(
      (r) =>
        r.url().endsWith("/api/benefits/hr/answer") &&
        r.request().method() === "POST",
      { timeout: 80000 },
    );
    modelRequests++;
    await page
      .getByRole("button", { name: "서버에 인사 질문 보내기", exact: true })
      .click();
    const response = await pending;
    const data = await response.json();
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
    await page.screenshot({
      path: "output/playwright/hr-portal-live-answer-desktop.png",
      fullPage: true,
    });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.screenshot({
      path: "output/playwright/hr-portal-live-answer-mobile.png",
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
      scope:
        "One actual UI/BFF/configured-model request and original-source display; not independent answer-quality evaluation or KTcs eligibility approval",
    };
  } catch (error) {
    return {
      status: "FAILED",
      error: error.message,
      actualAnswerRequests: modelRequests,
    };
  }
}

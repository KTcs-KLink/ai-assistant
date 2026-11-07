// Home interactions and read-only local BFF data. All answer POSTs are blocked;
// drafting a question must never invoke the model without the send action.
async function verifyHrHome(page) {
  const base = "http://127.0.0.1:8825",
    api = base + "/api/benefits";
  const checks = [],
    viewports = [],
    errors = [],
    requests = [];
  let blockedAnswerRequests = 0;
  const assert = (condition, message) => {
    if (!condition) throw Error(message);
  };
  const record = (name, mode = "actual UI and local BFF") =>
    checks.push({ name, mode, passed: true });
  page.setDefaultTimeout(20000);
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.pathname.startsWith("/api/benefits"))
      requests.push({
        path: url.pathname,
        method: request.method(),
        authorization: !!request.headers().authorization,
      });
  });
  await page.route(api + "/hr/answer", (route) => {
    blockedAnswerRequests++;
    return route.fulfill({
      status: 503,
      contentType: "application/json",
      body: '{"detail":"Home test blocks unintended model calls"}',
    });
  });
  async function home() {
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
    await page.locator(".hr-home").waitFor();
    const close = page.getByRole("button", { name: "안내 닫기", exact: true });
    if (await close.isVisible()) await close.click();
    await page.locator("body").ariaSnapshot();
  }
  try {
    await page.setViewportSize({ width: 1440, height: 1040 });
    await home();
    const readinessResponse = await page.request.get(api + "/hr/readiness");
    assert(readinessResponse.status() === 200, "Readiness unavailable");
    const readiness = await readinessResponse.json();
    const plansResponse = await page.request.get(api + "/hr/preparations");
    assert(plansResponse.status() === 200, "Preparation lookup failed");
    const plans = (await plansResponse.json()).plans;
    assert(
      (await page.locator(".hr-home-source").innerText()).includes(
        `${readiness.research.source_count}개 조문`,
      ),
      "Source count differs from actual service",
    );
    assert(
      (await page.locator("#hr-home-queue-title > span").innerText()) ===
        String(plans.length),
      "Preparation count fabricated",
    );
    await page.getByText("예시 카탈로그", { exact: true }).waitFor();
    assert(
      (await page.locator(".hr-home .p-card-value").count()) === 0,
      "Example monetary recommendation promoted into main home",
    );
    assert(
      (await page.locator(".hr-home-trust").innerText()).includes("미연결"),
      "Unconnected scope hidden",
    );
    record(
      "Real source/preparation counts and honest example/unconnected labels",
    );

    const question = "병가 증빙 제출 기준을 확인하고 싶어요.";
    await page
      .getByRole("textbox", { name: "궁금한 인사 질문", exact: true })
      .fill(question);
    await page
      .getByRole("button", { name: "AI 도우미로 이동", exact: true })
      .click();
    await page.waitForURL(base + "/hr/assistant");
    assert(
      (await page
        .getByRole("textbox", { name: "서버 인사 질문", exact: true })
        .inputValue()) === question,
      "Typed draft was lost",
    );
    await page.waitForFunction(() => !history.state?.usr?.draftQuestion);
    assert(
      !page.url().includes(encodeURIComponent(question)),
      "Question placed in URL",
    );
    assert(blockedAnswerRequests === 0, "Draft auto-submitted");
    record(
      "Typed question reaches assistant intact, not URL/history or automatic submission",
    );

    const expected = [
      "병가 때 진단서는 언제 제출해야 하나요?",
      "정기 급여 지급일은 언제인가요?",
      "업무 사정으로 휴게시간을 바꿀 수 있나요?",
    ];
    for (const text of expected) {
      await home();
      await page
        .locator(".hr-home-topic-list")
        .getByRole("button", { name: new RegExp(text.replace(/[?]/g, "\\?")) })
        .click();
      await page.waitForURL(base + "/hr/assistant");
      assert(
        (await page
          .getByRole("textbox", { name: "서버 인사 질문", exact: true })
          .inputValue()) === text,
        "Topic draft changed",
      );
    }
    assert(blockedAnswerRequests === 0, "Topic click auto-submitted");
    record(
      "Three topic prompts open the corresponding draft without model calls",
    );

    await home();
    await page
      .getByRole("navigation", { name: "업무 빠른 실행" })
      .getByRole("link", { name: /^휴가·근태/ })
      .click();
    await page.waitForURL(
      (url) =>
        url.pathname === "/hr/library" &&
        url.searchParams.get("tab") === "rules" &&
        url.searchParams.get("q") === "휴가",
    );
    assert(
      (await page
        .getByRole("textbox", { name: "서버 규정·양식 검색어", exact: true })
        .inputValue()) === "휴가",
      "Topic query not applied",
    );
    await home();
    await page
      .getByRole("navigation", { name: "업무 빠른 실행" })
      .getByRole("link", { name: /^양식·증빙/ })
      .click();
    await page.waitForURL(base + "/hr/library?tab=forms");
    await page
      .getByRole("button", { name: "회사 양식·준비", exact: true })
      .waitFor();
    assert(
      (await page
        .getByRole("button", { name: "회사 양식·준비", exact: true })
        .getAttribute("aria-pressed")) === "true",
      "Form tab not selected",
    );
    record("Work shortcuts preserve the actual library search and form tab");

    await page.route(api + "/hr/preparations", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          plans: [
            {
              id: "HOME-TEST-PROGRESS",
              title: "합성 화면 검사 · 증빙 준비",
              checklist: ["항목1", "항목2", "항목3"],
              checked: [0],
              stale: false,
            },
            {
              id: "HOME-TEST-STALE",
              title: "합성 화면 검사 · 조건 재확인",
              checklist: ["항목1"],
              checked: [],
              stale: true,
            },
          ],
        }),
      }),
    );
    await home();
    assert(
      (await page.locator(".hr-home-plan-list li").count()) === 2,
      "Preparation cards missing",
    );
    await page.getByText("1/3개 준비 항목 확인", { exact: true }).waitFor();
    await page.getByText("조건·규정 재확인 필요", { exact: true }).waitFor();
    await page.unroute(api + "/hr/preparations");
    record(
      "Preparation progress and invalidated conditions remain distinct",
      "synthetic read-only preparation response",
    );

    for (const path of ["/hr/preparations", "/hr/catalog"])
      await page.route(api + path, (route) =>
        route.fulfill({
          status: 503,
          contentType: "application/json",
          body: '{"detail":"Synthetic home failure check"}',
        }),
      );
    await home();
    assert(
      (await page.locator("#hr-home-queue-title > span").innerText()) === "—",
      "Failed count turned into zero",
    );
    await page
      .getByText("준비 목록을 불러오지 못했어요", { exact: true })
      .waitFor();
    await page
      .getByText(
        "추천을 불러오지 못했어요. AI 질문과 원문 검색은 계속 이용할 수 있어요.",
        { exact: true },
      )
      .waitFor();
    await page
      .getByRole("textbox", { name: "궁금한 인사 질문", exact: true })
      .fill(question);
    assert(
      await page
        .getByRole("button", { name: "AI 도우미로 이동", exact: true })
        .isEnabled(),
      "Catalog failure disabled independent AI entry",
    );
    for (const path of ["/hr/preparations", "/hr/catalog"])
      await page.unroute(api + path);
    record(
      "Partial service failure does not fabricate counts or block AI entry",
      "synthetic 503 responses",
    );

    await home();
    for (const width of [1920, 1440, 1024, 768, 390, 360]) {
      await page.setViewportSize({ width, height: width < 500 ? 844 : 1040 });
      await page.evaluate(() => {
        document.activeElement?.blur();
        window.scrollTo(0, 0);
      });
      await page.mouse.move(0, 0);
      const documentWidth = await page.evaluate(
        () => document.documentElement.scrollWidth,
      );
      assert(documentWidth <= width + 1, "Horizontal overflow at " + width);
      viewports.push({ width, documentWidth });
      if ([1440, 390].includes(width))
        await page.screenshot({
          path: "output/playwright/hr-home-after-" + width + ".png",
          fullPage: true,
        });
    }
    record("Home remains usable at six desktop/tablet/mobile widths");
    await page.setViewportSize({ width: 1440, height: 1040 });
    await page
      .getByRole("link", { name: "이전 홈 구성 보기", exact: true })
      .click();
    await page.waitForURL(base + "/hr/home-previous");
    await page.locator(".hr-summary-row").waitFor();
    assert(
      (await page.getByRole("heading", { level: 1 }).innerText()).includes(
        "오늘 필요한 인사 업무",
      ),
      "Previous home replaced",
    );
    record("Previous connected home remains reachable and unchanged");

    assert(blockedAnswerRequests === 0, "Unexpected automatic answer POST");
    assert(
      !requests.some(
        (r) => r.path === "/api/benefits/config" || r.authorization,
      ),
      "Cloud config probe or browser authorization header",
    );
    assert(!errors.length, "Browser errors: " + errors.join(";"));
    await home();
    return {
      status: "PASSED",
      checkedAt: new Date().toISOString(),
      checks,
      viewports,
      referenceSourceCount: readiness.research.source_count,
      actualPreparationCount: plans.length,
      pageErrors: errors,
      blockedAnswerRequests,
      newLlmAnswerRequests: 0,
      cloudConfigurationRequests: 0,
      scope:
        "Home UI/navigation/data-state verification; synthetic cases explicitly labeled; no new answer or retrieval benchmark",
    };
  } catch (error) {
    return {
      status: "FAILED",
      error: error.message,
      checks,
      viewports,
      pageErrors: errors,
      blockedAnswerRequests,
    };
  } finally {
    await page.unroute(api + "/hr/answer");
    for (const path of ["/hr/preparations", "/hr/catalog"])
      await page.unroute(api + path);
  }
}

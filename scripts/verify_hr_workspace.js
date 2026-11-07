// Real local demo-account CRUD and UI verification. Answer POSTs are intercepted
// to catch accidental model calls. Only this isolated QA session's plans are removed.
async function verifyHrWorkspace(page) {
  const base = "http://127.0.0.1:8825",
    api = base + "/api/benefits";
  const checks = [],
    widths = [],
    errors = [],
    createdIds = [];
  let blockedAnswers = 0,
    configurationRequests = 0,
    authorizationHeaders = 0;
  const assert = (value, message) => {
    if (!value) throw Error(message);
  };
  const record = (name, mode = "actual local demo BFF and UI") =>
    checks.push({ name, mode, passed: true });
  page.setDefaultTimeout(20000);
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("request", (request) => {
    const path = new URL(request.url()).pathname;
    if (path === "/api/benefits/config") configurationRequests++;
    if (path.startsWith("/api/benefits") && request.headers().authorization)
      authorizationHeaders++;
  });
  await page.route(api + "/hr/answer", (route) => {
    blockedAnswers++;
    return route.fulfill({
      status: 503,
      contentType: "application/json",
      body: '{"detail":"Unintended model calls are blocked by UI verification"}',
    });
  });
  async function home() {
    await page.goto(base + "/hr");
    await page.locator(".hr-saas").waitFor();
    await page.locator('.hr-saas[aria-busy="false"]').waitFor();
    const close = page.getByRole("button", { name: "안내 닫기", exact: true });
    if (await close.isVisible()) await close.click();
    await page.locator("body").ariaSnapshot();
  }
  async function dialogClosed() {
    await page.keyboard.press("Escape");
    await page.getByRole("dialog").waitFor({ state: "hidden" });
  }
  let seedCount = 0,
    patchVerified = false;
  try {
    await page.setViewportSize({ width: 1440, height: 1040 });
    // Start an explicitly isolated example session, never the user's in-app tab.
    await page.request.delete(api + "/session");
    await page.goto(base + "/hr");
    await page
      .getByRole("button", {
        name: "예시 직원으로 인사 기능 시작",
        exact: true,
      })
      .click();
    await page.locator(".hr-saas").waitFor();
    const ready = await (await page.request.get(api + "/hr/readiness")).json();
    const catalog = await (await page.request.get(api + "/hr/catalog")).json();
    const session = await (await page.request.get(api + "/session")).json();
    assert(
      session.mode === "demo" && catalog.synthetic === true,
      "Only an isolated example account may be seeded",
    );
    assert(
      (await page.locator(".ws-metrics").innerText()).includes(
        String(ready.research.source_count),
      ),
      "Source count mismatch",
    );
    assert(
      (await page.locator(".hr-saas .hr-home-hero").count()) === 0,
      "Presentation hero remains on workspace",
    );
    record("Working navigation, compact work dashboard and source metadata");

    const eligible = catalog.cards.filter(
      (card) => card.status === "eligible" && card.checklist.length,
    );
    const review = catalog.cards.find(
      (card) => card.status !== "eligible" && card.checklist.length,
    );
    assert(
      eligible.length >= 2 && review,
      "Example catalog does not support bounded workflow cases",
    );
    const seeded = [];
    for (const card of [eligible[0], eligible[1], review]) {
      const response = await page.request.post(
        api + "/hr/preparations/" + encodeURIComponent(card.id),
        {
          data: {
            conditions_revision: catalog.conditions_revision,
            policy_sha256: card.policy_sha256,
          },
        },
      );
      assert(response.status() === 200, "Example preparation creation failed");
      const plan = await response.json();
      seeded.push(plan);
      createdIds.push(plan.id);
    }
    seedCount = seeded.length;
    for (let index = 0; index < seeded[1].checklist.length; index++)
      assert(
        (
          await page.request.patch(api + "/hr/preparations/" + seeded[1].id, {
            data: { index, checked: true },
          })
        ).status() === 200,
        "Example ready-state setup failed",
      );
    await home();
    assert(
      (await page.locator(".ws-table-scroll tbody tr").count()) === 3,
      "Actual prepared rows missing",
    );
    await page
      .locator(".ws-work-name")
      .filter({ hasText: seeded[0].title })
      .click();
    const dialog = page.getByRole("dialog");
    await dialog
      .getByRole("heading", { name: seeded[0].title, exact: true })
      .waitFor();
    const patched = page.waitForResponse(
      (response) =>
        response.url().includes("/hr/preparations/" + seeded[0].id) &&
        response.request().method() === "PATCH",
    );
    await dialog.getByRole("checkbox").first().click();
    assert((await patched).status() === 200, "Checklist PATCH failed");
    await page.waitForFunction(
      () =>
        document.querySelector(".ws-detail-checklist input")?.checked === true,
    );
    await page.locator('.hr-saas[aria-busy="false"]').waitFor();
    const saved = (
      await (await page.request.get(api + "/hr/preparations")).json()
    ).plans.find((plan) => plan.id === seeded[0].id);
    assert(
      saved.checked.includes(0),
      "Checked item not persisted by local API",
    );
    patchVerified = true;
    await dialogClosed();
    await home();
    await page
      .locator(".ws-work-name")
      .filter({ hasText: seeded[0].title })
      .click();
    assert(
      await page.getByRole("dialog").getByRole("checkbox").first().isChecked(),
      "Checklist lost on refresh",
    );
    await page.screenshot({
      path: "output/playwright/hr-saas-checklist-1440.png",
      fullPage: true,
    });
    await dialogClosed();
    record(
      "Open exact work item, save checklist through real PATCH, retain it after refresh",
    );

    for (const name of ["진행 중", "준비 완료", "재확인 필요"]) {
      await page
        .locator(".ws-work-filters")
        .getByRole("button", { name: new RegExp("^" + name) })
        .click();
      assert(
        (await page.locator(".ws-table-scroll tbody tr").count()) === 1,
        "State filter failed: " + name,
      );
    }
    await page
      .locator(".ws-work-name")
      .filter({ hasText: seeded[2].title })
      .click();
    for (const box of await page
      .getByRole("dialog")
      .getByRole("checkbox")
      .all())
      assert(await box.isDisabled(), "Review item still editable");
    await dialogClosed();
    await page
      .locator(".ws-work-filters")
      .getByRole("button", { name: /^전체/ })
      .click();
    await page
      .getByRole("textbox", { name: "준비 업무명 검색", exact: true })
      .fill(seeded[0].title);
    assert(
      (await page.locator(".ws-table-scroll tbody tr").count()) === 1,
      "Work-name search failed",
    );
    await page
      .getByRole("textbox", { name: "준비 업무명 검색", exact: true })
      .fill("없는검사업무");
    await page
      .getByRole("button", { name: "필터 초기화", exact: true })
      .click();
    await page
      .getByRole("combobox", { name: "준비 업무 정렬", exact: true })
      .selectOption("progress");
    assert(
      (await page.locator(".ws-work-name").first().innerText()).includes(
        seeded[1].title,
      ),
      "Progress sorting failed",
    );
    record(
      "Status filters, work-name search, reset, progress sorting and review edit lock",
    );

    await page.keyboard.press("Control+k");
    await page
      .getByRole("dialog")
      .getByRole("textbox", { name: "찾을 규정이나 업무", exact: true })
      .fill("휴가");
    await page
      .getByRole("dialog")
      .getByRole("button", { name: "원문 검색", exact: true })
      .click();
    await page.waitForURL(
      (url) =>
        url.pathname === "/hr/library" && url.searchParams.get("q") === "휴가",
    );
    assert(
      (await page
        .getByRole("textbox", { name: "서버 규정·양식 검색어", exact: true })
        .inputValue()) === "휴가",
      "Global search query changed",
    );
    record("Ctrl+K searches the actual reference library");
    for (const question of [
      "병가 증빙 제출 기준을 알려주세요.",
      "정기 급여 지급일은 언제인가요?",
    ]) {
      await page
        .getByRole("button", { name: "업무 검색 열기", exact: true })
        .click();
      await page
        .getByRole("dialog")
        .getByRole("button", { name: "AI 질문 작성", exact: true })
        .click();
      await page
        .getByRole("dialog")
        .getByRole("textbox", { name: "궁금한 인사 질문", exact: true })
        .fill(question);
      await page
        .getByRole("dialog")
        .getByRole("button", { name: "질문 이어쓰기", exact: true })
        .click();
      await page.waitForURL(base + "/hr/assistant");
      await page.waitForFunction(
        (expected) =>
          document.querySelector("#hr-question")?.value === expected,
        question,
      );
      assert(
        (await page
          .getByRole("textbox", { name: "서버 인사 질문", exact: true })
          .inputValue()) === question,
        "Draft lost when navigating to existing assistant",
      );
      await page.waitForFunction(() => !history.state?.usr?.draftQuestion);
    }
    record(
      "Global AI drafts update even on the same assistant route, without automatic submission",
    );

    await page
      .getByRole("button", { name: "변경 안내 설정", exact: true })
      .click();
    const updatesBox = page.getByRole("dialog").getByRole("checkbox");
    const enabled = await page.request
      .get(api + "/hr/updates")
      .then((response) => response.json());
    if (!enabled.enabled) {
      const changed = page.waitForResponse(
        (response) =>
          response.url().endsWith("/hr/reminders") &&
          response.request().method() === "PUT",
      );
      await updatesBox.click();
      assert((await changed).status() === 200, "Update setting failed");
      await page.waitForFunction(
        () =>
          document.querySelector(".ws-updates-settings input")?.checked ===
          true,
      );
      await page.locator('.hr-saas[aria-busy="false"]').waitFor();
    }
    const current = await (await page.request.get(api + "/hr/updates")).json();
    assert(
      current.enabled === true && current.external_notifications_sent === false,
      "Local setting misrepresented external notifications",
    );
    await dialogClosed();
    record(
      "Change-notice settings use the current account API and send no external messages",
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
      assert(documentWidth <= width + 1, "Workspace overflow at " + width);
      widths.push({ width, documentWidth });
      if ([1440, 390].includes(width))
        await page.screenshot({
          path: "output/playwright/hr-saas-workspace-" + width + ".png",
          fullPage: true,
        });
    }
    await page
      .getByRole("button", { name: "업무 메뉴 열기", exact: true })
      .click();
    await page
      .getByRole("dialog")
      .getByRole("link", { name: "AI 업무 도우미", exact: true })
      .click();
    await page.waitForURL(base + "/hr/assistant");
    assert(
      (await page.getByRole("dialog").count()) === 0,
      "Mobile menu not closed",
    );
    for (const path of [
      "/library",
      "/preparations",
      "/profile",
      "/status",
      "/benefits",
    ]) {
      await page.goto(base + "/hr" + path);
      await page.locator(".hr-saas").waitFor();
      assert(
        (await page.evaluate(() => document.documentElement.scrollWidth)) <=
          361,
        "Inner page overflow: " + path,
      );
    }
    record(
      "Six dashboard widths, mobile navigation and five inner-page layouts",
    );

    await page.setViewportSize({ width: 1440, height: 1040 });
    await page.route(api + "/hr/preparations", (route) =>
      route.fulfill({
        status: 503,
        contentType: "application/json",
        body: '{"detail":"Synthetic preparation lookup failure"}',
      }),
    );
    await home();
    assert(
      (
        await page.locator(".ws-metrics > button strong").first().innerText()
      ).startsWith("—"),
      "Failed metric turned into zero",
    );
    await page
      .getByText("업무 목록을 불러오지 못했어요", { exact: true })
      .waitFor();
    await page.unroute(api + "/hr/preparations");
    record(
      "Failed preparation lookup stays unknown and retryable",
      "explicit synthetic 503 response",
    );

    for (const [path, selector] of [
      ["/home-benchmark", ".hr-home"],
      ["/home-previous", ".hr-summary-row"],
    ]) {
      await page.goto(base + "/hr" + path);
      await page.locator(selector).waitFor();
      assert(
        (await page.locator(".hr-saas").count()) === 0,
        "Legacy design was replaced by new shell",
      );
    }
    record("Both prior home designs remain in their original shell");
    assert(
      blockedAnswers === 0 &&
        configurationRequests === 0 &&
        authorizationHeaders === 0,
      "Unexpected provider/configuration/auth request",
    );
    assert(!errors.length, "Browser errors: " + errors.join(";"));
    return {
      status: "PASSED",
      checkedAt: new Date().toISOString(),
      checks,
      widths,
      examplePlansSeeded: seedCount,
      actualChecklistPatchVerified: patchVerified,
      blockedAnswers,
      newLlmAnswerRequests: 0,
      configurationRequests,
      browserAuthorizationHeaders: authorizationHeaders,
      pageErrors: errors,
      scope:
        "Local example-account work CRUD and UI verification; not production identity, tenant isolation, submissions or a new RAG evaluation",
    };
  } catch (error) {
    return {
      status: "FAILED",
      error: error.message,
      checks,
      widths,
      pageErrors: errors,
      examplePlansSeeded: seedCount,
      actualChecklistPatchVerified: patchVerified,
      blockedAnswers,
    };
  } finally {
    await page.unroute(api + "/hr/preparations");
    await page.unroute(api + "/hr/answer");
    for (const id of createdIds)
      await page.request.delete(
        api + "/hr/preparations/" + encodeURIComponent(id),
      );
    await page.request.put(api + "/hr/reminders", { data: { enabled: false } });
    await page.request.delete(api + "/session");
  }
}

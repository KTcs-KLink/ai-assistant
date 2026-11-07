// Playwright CLI run-code function. No paid model calls in this script.
async function verifyHrPortal(page) {
  const base = "http://127.0.0.1:8825",
    root = "/api/benefits",
    hr = root + "/hr";
  const checks = [],
    responsive = [],
    pageErrors = [],
    requests = [],
    external = [];
  const assert = (condition, message) => {
    if (!condition) throw Error(message);
  };
  const view = async () => {
    await page.evaluate(
      () =>
        new Promise((resolve) =>
          requestAnimationFrame(() => requestAnimationFrame(resolve)),
        ),
    );
    return page.locator("body").ariaSnapshot();
  };
  const text = async (value) =>
    page
      .getByText(value, { exact: false })
      .first()
      .waitFor({ state: "visible" });
  const idle = async () => {
    await page.locator('.hr-app[aria-busy="false"]').waitFor();
    await view();
  };
  const test = async (name, run, mode = "real BFF") => {
    await run();
    checks.push({ name, mode, passed: true });
  };
  const nav = async (path) => {
    const links = await page.locator('a[href="/hr' + path + '"]').all();
    for (const link of links)
      if (await link.isVisible()) {
        await link.click();
        await page.getByRole("heading", { level: 1 }).waitFor();
        await view();
        return;
      }
    throw Error("No visible route link: " + path);
  };
  const response = async (path, method, run, status = 200) => {
    const pending = page.waitForResponse(
      (r) => r.url().includes(path) && r.request().method() === method,
    );
    await run();
    const result = await pending;
    assert(
      result.status() === status,
      method + " " + path + " returned " + result.status(),
    );
    return result;
  };
  page.setDefaultTimeout(15000);
  page.on("pageerror", (error) => pageErrors.push(error.message));
  page.on("request", (r) => {
    const url = new URL(r.url());
    if (/^https?:$/.test(url.protocol) && url.origin !== base)
      external.push(url.origin + url.pathname);
    if (url.pathname.startsWith(root)) {
      let keys = [];
      if (r.postData())
        try {
          keys = Object.keys(JSON.parse(r.postData()));
        } catch {}
      requests.push({
        method: r.method(),
        path: url.pathname.replace(
          /(\/sources\/|\/preparations\/)[^/]+/g,
          "$1:id",
        ),
        bodyKeys: keys,
        authorizationHeaderPresent: !!r.headers().authorization,
      });
    }
  });
  let facts = {};
  try {
    await page.setViewportSize({ width: 1440, height: 1040 });
    await page.goto(base + "/hr");
    await page.getByRole("heading", { level: 1 }).waitFor();
    await view();
    if (
      await page
        .getByRole("button", { name: "접속 종료", exact: true })
        .isVisible()
    ) {
      await response(
        root + "/session",
        "DELETE",
        () =>
          page.getByRole("button", { name: "접속 종료", exact: true }).click(),
        204,
      );
      await page
        .getByRole("button", {
          name: "예시 직원으로 인사 기능 시작",
          exact: true,
        })
        .waitFor();
    }
    await test("Explicit example login, HttpOnly session and company SSO boundary", async () => {
      await text("회사 계정·SSO 로그인은 연결 전입니다.");
      assert(
        (await page.getByRole("textbox").count()) === 0,
        "Login must not collect credentials",
      );
      await page.screenshot({ path: "output/playwright/hr-portal-login.png" });
      await response(root + "/session/demo", "POST", () =>
        page
          .getByRole("button", {
            name: "예시 직원으로 인사 기능 시작",
            exact: true,
          })
          .click(),
      );
      await idle();
      await text("서버 연결 · 예시 직원 체험");
      const cookie = (await page.context().cookies()).find(
        (c) => c.name === "klink_benefits_session",
      );
      assert(
        cookie?.httpOnly &&
          cookie.sameSite === "Strict" &&
          cookie.path === root,
        "Session cookie attributes",
      );
      assert(
        !(await page.evaluate(() => document.cookie)).includes(
          "klink_benefits_session",
        ),
        "Session cookie readable by JS",
      );
      facts.cookie = {
        httpOnly: cookie.httpOnly,
        sameSite: cookie.sameSite,
        path: cookie.path,
      };
      const result = await page.request.get(base + hr + "/readiness");
      const data = await result.json();
      facts.readiness = {
        approvedPolicies: data.approved_policy_count,
        officialForms: data.official_form_count,
        referenceSources: data.research.source_count,
        humanApprovedSources: data.research.human_approved_count,
        productionReady: data.production_ready,
      };
    });
    await test("Home uses server recommendations and separates company applicability", async () => {
      await text("회사 승인 규정 0건");
      await text("공식 양식 0건");
      await text("회사 SSO 연결 전");
      assert(
        await page.getByRole("link", { name: /조건 충족.*3건/ }).isVisible(),
        "Server recommendation count missing",
      );
      await page.screenshot({
        path: "output/playwright/hr-portal-desktop.png",
        fullPage: true,
      });
      await nav("/status");
      await text("회사 승인 원문·답변");
      assert(
        (await page.locator(".hr-gates article").count()) === 6,
        "Six readiness gates missing",
      );
      await text("연결 전 · 예시 직원 접속과 구분");
      await page.screenshot({
        path: "output/playwright/hr-portal-status.png",
        fullPage: true,
      });
      await nav("");
    });
    await test("Version-bound preparation, server checklist and refresh persistence", async () => {
      await page
        .getByRole("button", { name: "자녀 돌봄 지원금", exact: true })
        .click();
      await view();
      const dialog = page.getByRole("dialog");
      await dialog
        .getByRole("button", { name: "근거 규정", exact: true })
        .click();
      await view();
      await text("DEMO-childcare");
      await text("가상 규정");
      await page.screenshot({ path: "output/playwright/hr-portal-policy.png" });
      await response(hr + "/preparations/", "POST", () =>
        dialog
          .getByRole("button", { name: "서버 준비 목록에 담기", exact: true })
          .click(),
      );
      await idle();
      await text("서버 준비 목록");
      const boxes = page.getByRole("checkbox");
      assert((await boxes.count()) === 3, "Expected 3 server checklist items");
      for (let i = 0; i < 3; i++) {
        await response(hr + "/preparations/", "PATCH", () =>
          boxes.nth(i).click(),
        );
        await idle();
      }
      await text("확인 표시 완료 · 회사 검토·승인과는 별도입니다.");
      assert(
        await page
          .getByRole("button", { name: "실제 신청·결재 연결 전", exact: true })
          .isDisabled(),
        "Real submission enabled",
      );
      await page.screenshot({
        path: "output/playwright/hr-portal-preparations.png",
        fullPage: true,
      });
      await page.reload();
      await page.getByRole("heading", { level: 1 }).waitFor();
      await idle();
      for (const box of await page.getByRole("checkbox").all())
        assert(await box.isChecked(), "Server checklist lost on refresh");
    });
    await test("Reminder opt-in, changed conditions and stale preparation invalidate old checks", async () => {
      await nav("");
      await response(hr + "/reminders", "PUT", () =>
        page
          .getByRole("checkbox", {
            name: "이 화면에서 변경·마감 안내 받기",
            exact: true,
          })
          .click(),
      );
      await idle();
      await text("예시 규정 일정");
      await nav("/profile");
      await page
        .getByRole("combobox", { name: "서버 고용형태", exact: true })
        .selectOption("fixed_term");
      await page
        .getByRole("textbox", { name: "서버 입사일", exact: true })
        .fill("2026-08-01");
      await response(root + "/profile", "PUT", () =>
        page
          .getByRole("button", { name: "서버에 조건 반영", exact: true })
          .click(),
      );
      await idle();
      await nav("/preparations");
      await text("조건·규정 재확인 필요");
      for (const box of await page.getByRole("checkbox").all()) {
        assert(await box.isDisabled(), "Stale checkbox active");
        assert(!(await box.isChecked()), "Stale check survived");
      }
      await nav("");
      await text("규정 또는 내 조건이 변경돼 다시 확인이 필요해요.");
    });
    await test("Official forms come from BFF and cannot download before connection", async () => {
      await nav("/library");
      await page
        .getByRole("button", { name: "회사 양식·준비", exact: true })
        .click();
      await view();
      await text("공식 파일 0개 연결");
      assert(
        (await page.locator(".p-document-row").count()) === 6,
        "Six form guides missing",
      );
      await page.getByRole("button", { name: /휴가신청서/ }).click();
      await view();
      await text("공식 파일 미연결 · 준비 안내");
      assert(
        await page
          .getByRole("button", {
            name: "공식 양식 연결 전 · 다운로드 불가",
            exact: true,
          })
          .isDisabled(),
        "Fake download available",
      );
      assert(
        (await page.locator("a[download]").count()) === 0,
        "Unexpected form file link",
      );
      await page.screenshot({ path: "output/playwright/hr-portal-forms.png" });
      await page.keyboard.press("Escape");
    });
    let verifiedSource = null;
    await test("Actual HR search and source lookup preserve KEPCO scope and metadata", async () => {
      await page
        .getByRole("button", { name: "참고 원문 검색", exact: true })
        .click();
      await view();
      await page
        .getByRole("textbox", { name: "서버 규정·양식 검색어", exact: true })
        .fill("병가");
      const found = await response(hr + "/evidence", "GET", () =>
        page.getByRole("button", { name: "검색", exact: true }).click(),
      );
      const data = await found.json();
      assert(
        data.results.length > 0 &&
          data.company === "KEPCO" &&
          !data.ktcs_applicable,
        "Reference search scope mismatch",
      );
      verifiedSource = data.results[0];
      await page.locator(".p-document-row").first().waitFor();
      await response(hr + "/sources/", "GET", () =>
        page.locator(".p-document-row").first().click(),
      );
      await page.getByRole("dialog").waitFor();
      await text("독립된 사람 승인 전");
      await text("KTcs 규정·자격에 적용할 수 있는지 확인되지 않았어요.");
      await page.screenshot({ path: "output/playwright/hr-portal-source.png" });
      await page.keyboard.press("Escape");
    });
    await test(
      "Unsupported question stays review-only without fabricated text",
      async () => {
        await nav("/assistant");
        const url = base + hr + "/answer";
        // Semantic mode uses a model even to classify outside-scope questions.
        // Keep this regression explicitly synthetic and free of provider calls.
        await page.route(url, (route) =>
          route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify({
              company: "KEPCO",
              ktcs_applicable: false,
              human_approved: false,
              employee_data_sent: false,
              status: "needs_review",
              paragraphs: [],
              sources: [],
              missing_information: [
                "허용된 인사 원문에서 필요한 근거를 찾지 못했어요.",
              ],
              notice:
                "화면 검사용 합성 응답 · 한국전력 참고자료 · KTcs 적용 미확인",
              understanding: {
                status: "out_of_scope",
                intents: [],
                interpreted_as: "",
                employment: "unspecified",
                explicit_conditions: [],
                clarification: "",
                original_question_preserved: true,
                employee_profile_sent: false,
                eligibility_decision: false,
              },
              provider_calls: [{ phase: "question_understanding" }],
            }),
          }),
        );
        try {
          await page
            .getByRole("textbox", { name: "서버 인사 질문", exact: true })
            .fill("안드로메다 은하의 별을 설명해 주세요");
          const result = await response(hr + "/answer", "POST", () =>
            page
              .getByRole("button", {
                name: "서버에 인사 질문 보내기",
                exact: true,
              })
              .click(),
          );
          const answer = await result.json();
          assert(
            answer.paragraphs.length === 0 && answer.status === "needs_review",
            "Unsupported answer was fabricated",
          );
          await text("허용된 인사 원문에서 필요한 근거를 찾지 못했어요.");
        } finally {
          await page.unroute(url);
        }
      },
      "intercepted synthetic scope response; no model call",
    );
    await test(
      "Withheld generated text stays hidden while real source remains readable",
      async () => {
        await page
          .getByRole("button", { name: "새 대화", exact: true })
          .click();
        const url = base + hr + "/answer";
        await page.route(url, (route) =>
          route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify({
              company: "KEPCO",
              ktcs_applicable: false,
              human_approved: false,
              employee_data_sent: false,
              status: "needs_review",
              paragraphs: [
                { text: "INVALID_DRAFT_MUST_NOT_RENDER", citations: [] },
              ],
              missing_information: ["추가 확인이 필요합니다."],
              sources: [verifiedSource],
              notice: "한국전력 참고자료 · KTcs 적용 미확인",
              validation: "REJECTED_DRAFT_WITHHELD_VERIFIED_SOURCES_AVAILABLE",
              generated_text_withheld: true,
            }),
          }),
        );
        await page
          .getByRole("textbox", { name: "서버 인사 질문" })
          .fill("검사 실패 화면 확인");
        await response(hr + "/answer", "POST", () =>
          page.getByRole("button", { name: "서버에 인사 질문 보내기" }).click(),
        );
        await text("생성 문장은 표시하지 않았어요.");
        assert(
          !(await page.locator("body").innerText()).includes(
            "INVALID_DRAFT_MUST_NOT_RENDER",
          ),
          "Withheld draft displayed",
        );
        await text("조회된 원문");
        await page.screenshot({
          path: "output/playwright/hr-portal-withheld.png",
          fullPage: true,
        });
        await page.unroute(url);
      },
      "intercepted response; no model call",
    );
    await test(
      "Provider/transport failure shows an error without a replacement answer",
      async () => {
        await page
          .getByRole("button", { name: "새 대화", exact: true })
          .click();
        const url = base + hr + "/answer";
        await page.route(url, (route) =>
          route.fulfill({
            status: 503,
            contentType: "application/json",
            body: JSON.stringify({
              detail: "연결 확인이 필요합니다. 잠시 후 다시 시도해 주세요.",
            }),
          }),
        );
        await page
          .getByRole("textbox", { name: "서버 인사 질문" })
          .fill("연결 실패 화면 확인");
        await response(
          hr + "/answer",
          "POST",
          () =>
            page
              .getByRole("button", { name: "서버에 인사 질문 보내기" })
              .click(),
          503,
        );
        await text("답변을 확인하지 못했어요");
        await text("확인되지 않은 답변을 대신 만들지 않습니다.");
        await page.unroute(url);
      },
      "intercepted 503; no model call",
    );
    await test(
      "Failed catalog lookup is not replaced by fictional local recommendations",
      async () => {
        await page.route(base + hr + "/catalog", (route) =>
          route.fulfill({
            status: 503,
            contentType: "application/json",
            body: JSON.stringify({ detail: "규정 상태 확인 필요" }),
          }),
        );
        await page.goto(base + "/hr");
        await text("혜택 추천을 조회하지 못했어요");
        assert(
          (await page.locator(".hr-benefit-card").count()) === 0,
          "Local fallback cards displayed",
        );
        await page.unroute(base + hr + "/catalog");
        await page.reload();
        await page.getByRole("heading", { level: 1 }).waitFor();
        await idle();
      },
      "intercepted catalog 503",
    );
    await test("Server consent revocation clears plans and reminders and survives refresh", async () => {
      await nav("/profile");
      await response(
        root + "/profile",
        "DELETE",
        () =>
          page
            .getByRole("button", {
              name: "서버 동의 철회·정보 비우기",
              exact: true,
            })
            .click(),
        204,
      );
      await idle();
      assert(
        !(await page
          .getByRole("checkbox", { name: "서버 근무 정보 활용 동의" })
          .isChecked()),
        "Work consent remains",
      );
      assert(
        !(await page
          .getByRole("checkbox", { name: "서버 가족 정보 활용 동의" })
          .isChecked()),
        "Family consent remains",
      );
      await nav("/preparations");
      await text("서버에 담은 준비 목록이 없어요");
      await nav("");
      assert(
        !(await page
          .getByRole("checkbox", { name: "이 화면에서 변경·마감 안내 받기" })
          .isChecked()),
        "Reminder consent remains",
      );
      await page.reload();
      await page.getByRole("heading", { level: 1 }).waitFor();
      await idle();
      assert(
        await page.getByRole("link", { name: /조건 충족.*0건/ }).isVisible(),
        "Revoked profile silently reset to fictional default",
      );
    });
    await test("Responsive connected pages have no horizontal overflow", async () => {
      for (const width of [1920, 1440, 1024, 768, 390, 360]) {
        await page.setViewportSize({
          width,
          height: width <= 390 ? 844 : 1040,
        });
        for (const route of [
          "",
          "/benefits",
          "/assistant",
          "/library",
          "/preparations",
          "/profile",
          "/status",
        ]) {
          await nav(route);
          const dimensions = await page.evaluate(() => ({
            viewport: innerWidth,
            document: document.documentElement.scrollWidth,
          }));
          assert(
            dimensions.document <= dimensions.viewport + 1,
            "Overflow: " + width + " " + route,
          );
          responsive.push({ width, route: "/hr" + route, ...dimensions });
          if (width === 390 && ["", "/status", "/profile"].includes(route))
            await page.screenshot({
              path:
                "output/playwright/hr-portal-mobile-" +
                (route.slice(1) || "home") +
                ".png",
              fullPage: !!route,
            });
        }
      }
    });
    await page.setViewportSize({ width: 1440, height: 1040 });
    await test("Logout invalidates server access and session expiry hides private screen", async () => {
      await response(
        root + "/session",
        "DELETE",
        () =>
          page.getByRole("button", { name: "접속 종료", exact: true }).click(),
        204,
      );
      await page
        .getByRole("button", { name: "예시 직원으로 인사 기능 시작" })
        .waitFor();
      assert(
        (await page.request.get(base + hr + "/catalog")).status() === 401,
        "Logout did not invalidate backend access",
      );
      await page.reload();
      await page
        .getByRole("button", { name: "예시 직원으로 인사 기능 시작" })
        .waitFor();
      assert(
        (await page.locator(".hr-benefit-card").count()) === 0,
        "Private cards remain after session expiry",
      );
    });
    assert(
      pageErrors.length === 0,
      "Browser script errors: " + pageErrors.join("; "),
    );
    assert(
      external.length === 0,
      "Browser contacted external origin: " + external.join("; "),
    );
    assert(
      requests.every((item) => !item.authorizationHeaderPresent),
      "Authorization header leaked to browser requests",
    );
    assert(
      requests
        .filter((item) => item.path === hr + "/answer")
        .every(
          (item) =>
            item.bodyKeys.length === 1 && item.bodyKeys[0] === "question",
        ),
      "Employee conditions sent to answer endpoint",
    );
    assert(
      await page.evaluate(
        () => localStorage.length === 0 && sessionStorage.length === 0,
      ),
      "Browser storage used for private data",
    );
    return {
      status: "PASSED",
      checkedAt: new Date().toISOString(),
      checks,
      responsive,
      facts,
      pageErrors,
      externalBrowserRequests: external,
      apiRequests: requests,
      paidModelCalls: 0,
      scope:
        "New UI with actual BFF plus separately labelled intercepted failure states; not company eligibility approval, independent answer-quality evaluation or physical device testing",
    };
  } catch (error) {
    return {
      status: "FAILED",
      error: error.message,
      checks,
      responsive,
      facts,
      pageErrors,
      apiRequests: requests,
    };
  }
}

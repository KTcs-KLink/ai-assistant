// Run through Playwright CLI: run-code --filename=scripts/verify_alternative_ui.js
// Browser-only verification of this fictional preview. No production API calls.
async function verifyAlternativePreview(page) {
  page.setDefaultTimeout(10000);
  const base = "http://127.0.0.1:8824";
  const checks = [],
    errors = [],
    external = [],
    api = [],
    responsive = [];
  const assert = (condition, message) => {
    if (!condition) throw new Error(message);
  };
  const snapshot = async () => {
    await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    return page.locator("body").ariaSnapshot();
  };
  const visibleText = async (text) => {
    await page.getByText(text, { exact: false }).first().waitFor({ state: "visible" });
  };
  const check = async (name, run) => {
    await run();
    checks.push({ name, passed: true });
  };
  const go = async (path) => {
    await page.goto(base + "/workspace" + path);
    await page.getByRole("heading", { level: 1 }).waitFor();
    await snapshot();
  };
  const nav = async (name) => {
    await page
      .getByRole("navigation", { name: "직원 포털 메뉴" })
      .getByRole("link", { name: new RegExp("^" + name) })
      .click();
    await snapshot();
  };
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (/^https?:$/.test(url.protocol) && url.origin !== base)
      external.push(url.origin + url.pathname);
    if (url.pathname.startsWith("/api/")) api.push(url.pathname);
  });
  try {
    await page.setViewportSize({ width: 1440, height: 1040 });
    await go("");
    await check(
      "Desktop home: fictional profile and recommendation counts",
      async () => {
        await visibleText("체험 직원님.");
        await visibleText("가상 규정 기준");
        assert(
          await page.getByRole("link", { name: /조건 충족 3/ }).isVisible(),
          "Initial eligible count must be 3",
        );
        await page.screenshot({ path: "output/playwright/desktop-home.png" });
        await page.screenshot({
          path: "output/playwright/desktop-home-full.png",
          fullPage: true,
        });
      },
    );
    await page
      .getByRole("button", { name: "자녀 돌봄 지원금", exact: true })
      .click();
    await snapshot();
    const dialog = page.getByRole("dialog");
    await check(
      "Benefit explanation, source metadata, save and keyboard focus trap",
      async () => {
        await dialog
          .getByRole("button", { name: "추천 이유", exact: true })
          .click();
        await snapshot();
        await visibleText("만 5세 자녀가 예시 연령 조건에 맞아요.");
        await dialog
          .getByRole("button", { name: "근거 규정", exact: true })
          .click();
        await snapshot();
        await visibleText("DEMO-childcare");
        await visibleText("KTcs 적용 미확인");
        await page.screenshot({ path: "output/playwright/desktop-source.png" });
        for (let i = 0; i < 12; i++) await page.keyboard.press("Tab");
        assert(
          await page.evaluate(
            () => !!document.activeElement?.closest("dialog"),
          ),
          "Dialog focus escaped",
        );
        await dialog
          .getByRole("button", { name: "자녀 돌봄 지원금 저장", exact: true })
          .click();
        await dialog
          .getByRole("button", { name: "신청 준비에 담기", exact: true })
          .click();
        await snapshot();
      },
    );
    await check(
      "Preparation checks remain preparation, with no submission claim",
      async () => {
        assert(
          page.url().endsWith("/preparations"),
          "Preparation route missing",
        );
        const boxes = page.getByRole("checkbox");
        assert((await boxes.count()) === 3, "Expected 3 checklist items");
        for (const box of await boxes.all()) await box.check();
        await visibleText(
          "확인 표시만 완료되었습니다. 회사의 검토·승인은 별도입니다.",
        );
        await page.screenshot({
          path: "output/playwright/desktop-preparations.png",
        });
      },
    );
    await nav("맞춤 혜택");
    await check(
      "Saved, needs-review, ineligible and no-results benefit filters",
      async () => {
        await page.getByRole("button", { name: /^저장한 혜택/ }).click();
        await snapshot();
        assert(
          (await page.getByRole("article").count()) === 1,
          "Saved card missing",
        );
        await page.getByRole("button", { name: /^추가 확인/ }).click();
        await snapshot();
        assert(
          (await page.getByRole("article").count()) === 2,
          "Needs-review filter count",
        );
        await page
          .getByRole("button", { name: "주거 안심 지원", exact: true })
          .click();
        await snapshot();
        await visibleText("금액·요건 미확정");
        await dialog
          .getByRole("button", { name: "추천 이유", exact: true })
          .click();
        await visibleText(
          "소득·주택·중복 지원 조건을 담당 부서에 확인해야 해요.",
        );
        await page.keyboard.press("Escape");
        await page.getByRole("button", { name: /^해당 없음/ }).click();
        await snapshot();
        await page
          .getByRole("button", { name: "오래 함께한 당신에게", exact: true })
          .click();
        await snapshot();
        await visibleText("만 7년 근속 · 10년 이상 조건이에요.");
        await page.keyboard.press("Escape");
        await page.getByRole("button", { name: /^전체/ }).click();
        await page
          .getByRole("textbox", { name: "혜택 검색", exact: true })
          .fill("존재하지않는제도");
        await visibleText("조건에 맞는 결과가 없어요");
        await page
          .getByRole("textbox", { name: "혜택 검색", exact: true })
          .fill("");
        await snapshot();
        await page.screenshot({
          path: "output/playwright/desktop-benefits.png",
          fullPage: true,
        });
      },
    );
    await nav("규정·양식");
    await check(
      "Regulation search and form guide accurately identify unconnected official files",
      async () => {
        await page
          .getByRole("textbox", { name: "규정·양식 검색", exact: true })
          .fill("휴가");
        await snapshot();
        await page
          .getByRole("button", { name: /휴가·휴직.*가족 돌봄 휴가/ })
          .click();
        await snapshot();
        await visibleText("DEMO-family-leave");
        await page.keyboard.press("Escape");
        await page.getByRole("button", { name: /^양식 준비 가이드/ }).click();
        await page
          .getByRole("textbox", { name: "규정·양식 검색", exact: true })
          .fill("출장");
        await snapshot();
        await page.getByRole("button", { name: /출장비 정산서/ }).click();
        await snapshot();
        await visibleText("양식 준비 가이드 · 공식 양식 아님");
        await visibleText("영수증과 지출 내역");
        await visibleText("실제 서식은 담당 부서에서 확인");
        await page.screenshot({
          path: "output/playwright/desktop-form-guide.png",
        });
        await page.keyboard.press("Escape");
      },
    );
    await check(
      "Global keyboard search and Escape restore a usable page",
      async () => {
        await page.keyboard.press("Control+k");
        await snapshot();
        await dialog
          .getByRole("textbox", { name: "통합 검색어", exact: true })
          .fill("돌봄");
        await snapshot();
        assert(
          await dialog
            .getByRole("button", { name: /자녀 돌봄 지원금/ })
            .isVisible(),
          "Global search result missing",
        );
        await page.keyboard.press("Escape");
        assert((await dialog.count()) === 0, "Escape did not close dialog");
      },
    );
    await nav("AI 업무 도우미");
    await check(
      "AI fixture answer cites fictional evidence; unsupported questions withhold",
      async () => {
        await page
          .getByRole("button", {
            name: "자녀 돌봄 지원금 조건이 궁금해요",
            exact: true,
          })
          .click();
        await snapshot();
        await visibleText("가상 규정에 따른 예시 안내입니다.");
        await visibleText("DEMO-childcare");
        await page.screenshot({
          path: "output/playwright/desktop-assistant.png",
          fullPage: true,
        });
        await page
          .getByRole("textbox", { name: "업무 질문", exact: true })
          .fill("내 연봉이 정확히 얼마인가요?");
        await page
          .getByRole("button", { name: "질문 보내기", exact: true })
          .click();
        await snapshot();
        await visibleText(
          "이 질문에 답할 수 있는 회사 규정이 연결되지 않았습니다.",
        );
      },
    );
    await page
      .getByRole("link", { name: "내 정보·동의 관리", exact: true })
      .click();
    await snapshot();
    await check(
      "Consent gates profile values, recomputes recommendations and clears preparation checks",
      async () => {
        await page
          .getByRole("combobox", { name: "가상 고용형태", exact: true })
          .selectOption("fixed_term");
        await page
          .getByRole("combobox", { name: "가상 입사일", exact: true })
          .selectOption("2026-08-01");
        await page
          .getByRole("checkbox", {
            name: "가상 가족 정보 활용 동의",
            exact: true,
          })
          .uncheck();
        assert(
          await page
            .getByRole("combobox", { name: "가상 자녀 나이", exact: true })
            .isDisabled(),
          "Family input still enabled",
        );
        await page
          .getByRole("button", { name: "선택한 조건 반영", exact: true })
          .click();
        await nav("준비 목록");
        assert(
          (await page.getByRole("checkbox").count()) === 3,
          "Prepared checklist missing",
        );
        for (const box of await page.getByRole("checkbox").all())
          assert(
            !(await box.isChecked()),
            "Stale checklist survived condition change",
          );
        await page
          .getByRole("link", { name: "내 정보·동의 관리", exact: true })
          .click();
        await snapshot();
        await page
          .getByRole("button", {
            name: "동의 철회·예시 정보 비우기",
            exact: true,
          })
          .click();
        await visibleText("철회했습니다.");
        await nav("준비 목록");
        await visibleText("준비할 혜택을 담아보세요");
        await nav("AI 업무 도우미");
        await visibleText("어떤 일이 궁금하세요?");
        await nav("맞춤 혜택");
        assert(
          await page
            .getByRole("button", { name: /^조건 충족\s*0$/ })
            .isVisible(),
          "Revoked profile still eligible",
        );
        assert(
          await page
            .getByRole("button", { name: /^추가 확인\s*6$/ })
            .isVisible(),
          "Unknown conditions were not withheld",
        );
        await page.reload();
        await page.getByRole("heading", { level: 1 }).waitFor();
        assert(
          await page
            .getByRole("button", { name: /^조건 충족\s*3$/ })
            .isVisible(),
          "Refresh must restore fictional defaults",
        );
        assert(
          await page.evaluate(
            () => localStorage.length === 0 && sessionStorage.length === 0,
          ),
          "Preview stored browser data",
        );
      },
    );
    await check(
      "Fictional login preview starts without credentials",
      async () => {
        await page
          .getByRole("link", { name: "로그인 미리보기", exact: true })
          .click();
        await snapshot();
        await visibleText("실제 계정·비밀번호를 입력하지 않습니다.");
        assert(
          (await page.getByRole("textbox").count()) === 0,
          "Login accepts credentials",
        );
        await page.screenshot({ path: "output/playwright/desktop-login.png" });
        await page
          .getByRole("link", { name: "가상 직원으로 시작", exact: true })
          .click();
        await snapshot();
      },
    );
    const routes = [
      "",
      "/benefits",
      "/assistant",
      "/library",
      "/preparations",
      "/profile",
      "/login",
    ];
    await check(
      "Responsive layouts across desktop, tablet and phone widths",
      async () => {
        for (const width of [1920, 1440, 1024, 768, 390, 360]) {
          await page.setViewportSize({
            width,
            height: width <= 390 ? 844 : 1040,
          });
          for (const path of routes) {
            await go(path);
            const dimensions = await page.evaluate(() => ({
              viewport: innerWidth,
              document: document.documentElement.scrollWidth,
            }));
            assert(
              dimensions.document <= dimensions.viewport + 1,
              "Horizontal overflow at " + width + " " + path,
            );
            responsive.push({
              width,
              path: "/workspace" + path,
              ...dimensions,
            });
            if (width === 390 || width === 1440) {
              const suffix = path.slice(1) || "home";
              if (path === "/profile" || path === "/library" || width === 390)
                await page.screenshot({
                  path:
                    "output/playwright/" +
                    (width === 390 ? "mobile" : "desktop") +
                    "-" +
                    suffix +
                    ".png",
                  fullPage: path === "/profile" || path === "/library",
                });
            }
          }
        }
      },
    );
    await check(
      "Mobile drawer, preparation and bottom navigation",
      async () => {
        await page.setViewportSize({ width: 390, height: 844 });
        await go("");
        await page
          .getByRole("button", { name: "휴가 조건 확인", exact: true })
          .click();
        await snapshot();
        await dialog
          .getByRole("button", { name: "추천 이유", exact: true })
          .click();
        await snapshot();
        await page.screenshot({ path: "output/playwright/mobile-drawer.png" });
        const dimensions = await dialog.evaluate((el) => ({
          width: el.clientWidth,
          scroll: el.scrollWidth,
        }));
        assert(
          dimensions.scroll <= dimensions.width + 1,
          "Mobile drawer overflows",
        );
        await dialog
          .getByRole("button", { name: "신청 준비에 담기", exact: true })
          .click();
        await snapshot();
        await page.getByRole("checkbox").first().check();
        await page.screenshot({
          path: "output/playwright/mobile-preparation-active.png",
          fullPage: true,
        });
        await page
          .getByRole("navigation", { name: "모바일 주요 메뉴" })
          .getByRole("link", { name: "혜택", exact: true })
          .click();
        await snapshot();
        await page
          .getByRole("button", { name: "자녀 돌봄 지원금", exact: true })
          .click();
        await snapshot();
        await dialog
          .getByRole("link", { name: "AI 질문", exact: true })
          .click();
        await snapshot();
        assert(
          (
            await page.getByRole("textbox", { name: "업무 질문" }).inputValue()
          ).includes("자녀 돌봄 지원금"),
          "AI question prefill missing",
        );
        await page.getByRole("button", { name: "질문 보내기" }).click();
        await snapshot();
        await visibleText("가상 규정에 따른 예시 안내입니다.");
        await page.screenshot({
          path: "output/playwright/mobile-assistant-answer.png",
          fullPage: true,
        });
      },
    );
    assert(errors.length === 0, "Browser errors: " + errors.join("; "));
    assert(
      external.length === 0,
      "External requests detected: " + external.join("; "),
    );
    assert(api.length === 0, "Preview called backend API");
    checks.push({
      name: "No browser errors, external HTTP requests or backend/API calls",
      passed: true,
    });
    await page.setViewportSize({ width: 1440, height: 1040 });
    await go("");
    return {
      status: "PASSED",
      checkedAt: new Date().toISOString(),
      checks,
      responsive,
      pageErrors: errors,
      externalRequests: external,
      apiRequests: api,
      scope:
        "UI/interaction/responsive preview verification; not retrieval quality, answer correctness, company eligibility or backend integration approval",
    };
  } catch (error) {
    return {
      status: "FAILED",
      error: error.message,
      checks,
      responsive,
      pageErrors: errors,
      externalRequests: external,
      apiRequests: api,
    };
  }
}

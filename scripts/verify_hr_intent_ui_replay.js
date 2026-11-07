// Every answer POST is intercepted. Ready text is retained from an actual response;
// clarification/scope and tampering cases are explicitly synthetic transport fixtures.
async function verifyHrIntentReplay(page) {
  const fixture = /* RETAINED_INTENT_RESPONSE */ {};
  if (!fixture.question || !fixture.response?.understanding)
    throw Error("Prepare retained fixture first; no model calls made");
  const base = "http://127.0.0.1:8825",
    route = base + "/api/benefits/hr/answer";
  const checks = [],
    errors = [];
  let intercepted = 0;
  const clone = (value) => JSON.parse(JSON.stringify(value));
  const check = (condition, message) => {
    if (!condition) throw Error(message);
  };
  page.on("pageerror", (error) => errors.push(error.message));
  page.setDefaultTimeout(20000);
  await page.setViewportSize({ width: 1440, height: 1040 });
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
  const closeNotice = page.getByRole("button", { name: "안내 닫기", exact: true });
  if (await closeNotice.isVisible()) await closeNotice.click();
  await page
    .getByRole("navigation", { name: "인사 포털 메뉴" })
    .getByRole("link", { name: "AI 업무 도우미", exact: true })
    .click();
  async function show(
    data,
    question = fixture.question,
    preserveValidation = false,
  ) {
    if (!preserveValidation)
      data.validation = "FINAL_DETERMINISTIC_REVALIDATION_NOT_NEW_GENERATION";
    await page.unroute(route);
    await page.route(route, (r) => {
      intercepted++;
      return r.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(data),
      });
    });
    await page.getByRole("button", { name: "새 대화", exact: true }).click();
    await page
      .getByRole("textbox", { name: "서버 인사 질문", exact: true })
      .fill(question);
    await page
      .getByRole("button", { name: "서버에 인사 질문 보내기", exact: true })
      .click();
    await page
      .getByRole("button", { name: "서버에 인사 질문 보내기", exact: true })
      .filter({ hasText: "질문 보내기" })
      .waitFor();
  }
  const record = (name, mode) => checks.push({ name, mode, passed: true });
  try {
    await show(clone(fixture.response));
    await page.locator(".hr-answer-part").first().waitFor();
    check(
      (await page.locator(".hr-question-understanding").innerText()) ===
        "질문을 이렇게 이해했어요: " +
          fixture.response.understanding.interpreted_as,
      "Meaning label missing",
    );
    await page
      .getByText("보존 응답 재생 · 새 모델 호출 아님", { exact: true })
      .waitFor();
    record(
      "retained actual meaning label and cited answer",
      "actual response replay",
    );

    const facts = clone(fixture.response);
    facts.answer_method = "SOURCE_EXTRACTED_FACTS";
    facts.validation = "SOURCE_EXTRACTED_DAY_AND_EXCEPTION_NOT_HUMAN_APPROVAL";
    facts.provider_calls = [{ phase: "question_understanding" }];
    facts.notice = "합성 전송 형식 검사 · 한국전력 참고자료 · KTcs 적용 미확인";
    await show(facts, fixture.question, true);
    await page.locator(".hr-answer-part").first().waitFor();
    await page
      .getByText("지급일·예외를 원문에서 직접 확인한 안내입니다.", {
        exact: true,
      })
      .waitFor();
    record(
      "source-extracted contract accepts one analysis phase",
      "synthetic source-fact transport, not a new backend answer",
    );

    const clarification = clone(fixture.response);
    Object.assign(clarification, {
      status: "answered",
      paragraphs: [],
      sources: [],
      source_conditions: [],
      provider_calls: [{ phase: "question_understanding" }],
      notice: "화면 확인용 합성 응답 · 한국전력 참고자료 · KTcs 적용 미확인",
      understanding: {
        status: "needs_clarification",
        intents: ["annual_leave_entitlement"],
        interpreted_as: "연차휴가 일수",
        employment: "unspecified",
        explicit_conditions: [],
        clarification: "연차 일수와 사용 시기 중 무엇이 궁금하세요?",
        original_question_preserved: true,
        employee_profile_sent: false,
        eligibility_decision: false,
      },
    });
    delete clarification.quote_method;
    clarification.missing_information = [
      clarification.understanding.clarification,
    ];
    await show(clone(clarification), "연차가 궁금해요.");
    await page.getByText("질문 확인 필요", { exact: true }).waitFor();
    check(
      (await page
        .getByText(clarification.understanding.clarification, { exact: true })
        .count()) === 1,
      "Clarification missing or duplicated",
    );
    check(
      (await page
        .locator(
          ".hr-answer-part,.hr-question-understanding,.hr-answer-sources,.hr-condition-quote",
        )
        .count()) === 0,
      "Clarification displayed a regulation answer",
    );
    record(
      "clarification only, no answer/source/duplicate and no answered promotion",
      "synthetic clarification transport",
    );
    for (const width of [1440, 390]) {
      await page.setViewportSize({ width, height: width === 390 ? 844 : 1040 });
      check(
        (await page.evaluate(() => document.documentElement.scrollWidth)) <=
          width + 1,
        "Clarification overflow",
      );
      await page.screenshot({
        path: "output/playwright/hr-intent-clarification-" + width + ".png",
        fullPage: true,
      });
      await page.evaluate(() => { document.activeElement?.blur(); window.scrollTo(0, 0); });
      await page.mouse.move(0, 0);
    }
    const outside = clone(clarification);
    outside.understanding = {
      ...outside.understanding,
      status: "out_of_scope",
      intents: [],
      interpreted_as: "",
      clarification: "",
    };
    outside.missing_information = [
      "허용된 인사 업무 범위의 질문을 입력해 주세요.",
    ];
    await show(outside, "은하의 별에 대해 알려주세요.");
    await page.getByText("추가 확인 필요", { exact: true }).waitFor();
    check(
      (await page
        .locator(
          ".hr-answer-part,.hr-question-understanding,.hr-answer-sources,.hr-clarification",
        )
        .count()) === 0,
      "Outside-scope answer fabricated",
    );
    record(
      "outside scope remains review-only without regulation text",
      "synthetic scope transport",
    );

    for (const [name, change, question] of [
      [
        "condition absent from original question",
        (d) => (d.understanding.explicit_conditions = ["원질문에 없는 999일"]),
      ],
      [
        "original question not preserved",
        (d) => (d.understanding.original_question_preserved = false),
      ],
      [
        "unrecognized intent",
        (d) => (d.understanding.intents = ["invented_policy"]),
      ],
      [
        "answer without comparison phase",
        (d) =>
          (d.provider_calls = [
            { phase: "question_understanding" },
            { phase: "draft" },
          ]),
      ],
      [
        "clarification with generated answer",
        (d) => (d.understanding = clone(clarification.understanding)),
        "연차가 궁금해요.",
      ],
      ["malformed provider phase array", (d) => (d.provider_calls = {})],
      [
        "source-extracted method with generation phases",
        (d) => (d.answer_method = "SOURCE_EXTRACTED_FACTS"),
      ],
    ]) {
      const data = clone(fixture.response);
      change(data);
      await show(data, question ?? fixture.question);
      await page.locator(".hr-conversation .hr-errors").waitFor();
      check(
        (await page
          .locator(
            ".hr-answer-part,.hr-question-understanding,.hr-condition-quote,.hr-retrieval-trace",
          )
          .count()) === 0,
        "Invalid response rendered: " + name,
      );
      record(name, "tampered retained transport");
    }
    check(intercepted === checks.length, "Unexpected answer traffic");
    check(!errors.length, "Browser errors: " + errors.join(";"));
    return {
      status: "PASSED",
      checkedAt: new Date().toISOString(),
      checks,
      interceptedAnswerRequests: intercepted,
      newModelGenerations: 0,
      pageErrors: errors,
      scope:
        "Bounded UI protocol/clarification guards; synthetic cases do not establish model intent accuracy",
    };
  } finally {
    await page.unroute(route);
  }
}

// Actual expanded-scope GETs and explicitly synthetic answer-boundary tests.
// Ordinary answer POSTs are intercepted. One named-held question reaches the
// real backend and must prove zero provider calls; no model generations here.
async function verifyExpandedScopeUi(page) {
  const fixture = /* RETAINED_SCOPE_FIXTURE */ {};
  if (!fixture.response)
    throw Error("Prepare retained fixture first; no model calls");
  const base = "http://127.0.0.1:8825",
    api = base + "/api/benefits";
  const checks = [],
    widths = [],
    errors = [],
    requests = [];
  let answerPosts = 0,
    reviewFixture = null,
    heldReceipt = null,
    actualHeldPosts = 0;
  const heldQuestion = "단시간근로자 운영지침의 근무시간은 어떻게 되나요?";
  let allowHeld = false;
  const clone = (value) => JSON.parse(JSON.stringify(value));
  const assert = (value, message) => {
    if (!value) throw Error(message);
  };
  const record = (name, mode = "actual local expanded-service GETs and UI") =>
    checks.push({ name, mode, passed: true });
  let answerFixture = clone(fixture.response);
  answerFixture.validation =
    "FINAL_DETERMINISTIC_REVALIDATION_NOT_NEW_GENERATION";
  answerFixture.retrieval = {
    ...answerFixture.retrieval,
    source_scope: "expanded",
    source_count: 528,
    review_only_count: 3334,
  };
  answerFixture.sources.forEach((source) =>
    Object.assign(source, {
      answer_eligible: true,
      review_only: false,
      source_mapping_verified: true,
    }),
  );
  let currentAnswer = clone(answerFixture);
  page.setDefaultTimeout(20000);
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("request", (request) => {
    const path = new URL(request.url()).pathname;
    if (path.startsWith("/api/benefits"))
      requests.push({
        path,
        method: request.method(),
        auth: !!request.headers().authorization,
      });
  });
  await page.route(api + "/hr/answer", (route) => {
    if (
      allowHeld &&
      route.request().postDataJSON()?.question === heldQuestion
    ) {
      allowHeld = false;
      actualHeldPosts++;
      return route.continue();
    }
    answerPosts++;
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(currentAnswer),
    });
  });
  async function send(data) {
    currentAnswer = clone(data);
    await page.getByRole("button", { name: "새 대화", exact: true }).click();
    await page
      .getByRole("textbox", { name: "인사 질문", exact: true })
      .fill(fixture.question);
    await page
      .getByRole("button", { name: "인사 질문 전송", exact: true })
      .click();
    await page
      .getByRole("button", { name: "인사 질문 전송", exact: true })
      .waitFor();
  }
  try {
    await page.setViewportSize({ width: 1440, height: 1040 });
    await page.goto(base + "/hr");
    await page.getByRole("heading", { level: 1 }).waitFor();
    const login = page.getByRole("button", {
      name: "예시 직원으로 인사 기능 시작",
      exact: true,
    });
    if (await login.isVisible()) await login.click();
    await page.locator(".hr-saas").waitFor();
    const caps = await (
      await page.request.get(api + "/hr/capabilities")
    ).json();
    const ready = await (await page.request.get(api + "/hr/readiness")).json();
    assert(
      caps.source_scope === "expanded" &&
        ready.research.source_scope === "expanded",
      "Proxy still points at baseline service",
    );
    assert(
      ready.research.source_count === 528 &&
        ready.research.review_only_count === 3334 &&
        ready.research.human_approved_count === 0,
      "Unexpected source scope counts",
    );
    assert(
      (await page.locator(".ws-metrics").innerText()).includes("528") &&
        (await page.locator(".ws-review-scope").innerText()).includes("3,334"),
      "Home does not distinguish counts",
    );
    record(
      "Expanded capability and live 528/3334 counts, human approval remains zero",
    );

    await page.goto(
      base +
        "/hr/library?tab=rules&q=" +
        encodeURIComponent("상임임원 복무규정"),
    );
    await page.locator(".p-document-row").first().waitFor();
    const ordinary = await (
      await page.request.get(
        api + "/hr/evidence?q=" + encodeURIComponent("상임임원 복무규정"),
      )
    ).json();
    assert(
      ordinary.source_scope === "expanded" &&
        ordinary.results.some((source) =>
          source.title.includes("상임임원 복무규정"),
        ),
      "Newly included HR document not retrieved",
    );
    assert(
      ordinary.results.every(
        (source) =>
          source.answer_eligible === true &&
          source.review_only === false &&
          source.source_mapping_verified === true,
      ),
      "Held data mixed into answer search",
    );
    await page.locator(".p-document-row").first().click();
    await page.getByRole("dialog").waitFor();
    assert(
      (await page.locator(".hr-original").textContent()) ===
        ordinary.results[0].text,
      "Expanded ordinary original changed",
    );
    await page.keyboard.press("Escape");
    record(
      "Additional executive-service document and ordinary source lookup retain positive eligibility flags",
    );

    await page
      .getByRole("button", { name: "검토 전용 발췌", exact: true })
      .click();
    await page
      .getByRole("textbox", { name: "검토 발췌 검색어", exact: true })
      .fill("단시간근로자 운영지침");
    const searched = page.waitForResponse((response) =>
      response.url().includes("/hr/review-evidence?q="),
    );
    await page
      .locator(".hr-review-evidence")
      .getByRole("button", { name: "검색", exact: true })
      .click();
    const reviewResponse = await searched;
    reviewFixture = await reviewResponse.json();
    assert(
      reviewResponse.status() === 200 &&
        reviewFixture.answer_eligible === false &&
        reviewFixture.used_for_generation === false &&
        reviewFixture.results.length,
      "Review-only response contract missing",
    );
    await page.locator(".hr-review-excerpt").first().waitFor();
    await page.locator(".hr-review-excerpt > summary").first().click();
    assert(
      (await page
        .locator(".hr-review-excerpt blockquote")
        .first()
        .textContent()) === reviewFixture.results[0].text,
      "Review excerpt changed",
    );
    assert(
      reviewFixture.results.every(
        (item) =>
          item.excerpt_only === true && Array.isArray(item.hold_reasons),
      ),
      "Review excerpt/reason metadata missing",
    );
    assert(
      (await page.locator(".hr-review-holds").first().innerText()).includes(
        "구조",
      ),
      "Hold reasons not presented in Korean",
    );
    assert(
      (await page
        .locator(
          ".hr-review-evidence .sa-citations,.hr-review-evidence .sa-answer-part,.hr-review-evidence button",
        )
        .count()) === 1,
      "Review has answer/source selection actions",
    );
    assert(answerPosts === 0, "Review search initiated answer generation");
    await page.locator(".hr-review-excerpt > summary").first().click();
    record(
      "Review-only GET shows exact excerpt, review warning and no generation action",
    );
    for (const width of [1440, 768, 390, 360]) {
      await page.setViewportSize({ width, height: width < 500 ? 844 : 1040 });
      await page.evaluate(() => {
        document.activeElement?.blur();
        window.scrollTo(0, 0);
      });
      await page.mouse.move(0, 0);
      const documentWidth = await page.evaluate(
        () => document.documentElement.scrollWidth,
      );
      assert(documentWidth <= width + 1, "Scope library overflow at " + width);
      widths.push({ width, documentWidth });
      if ([1440, 390].includes(width))
        await page.screenshot({
          path: "output/playwright/hr-expanded-review-" + width + ".png",
          fullPage: true,
        });
    }
    record("Answer/review labels remain clear at four desktop/mobile widths");

    await page.setViewportSize({ width: 1440, height: 1040 });
    await page.goto(base + "/hr/assistant");
    await page.locator(".sa-assistant").waitFor();
    await page
      .getByRole("button", { name: "검토 전용 3,334구간", exact: true })
      .click();
    await page
      .getByRole("textbox", { name: "검토 발췌 검색어", exact: true })
      .fill("단시간");
    await page
      .locator(".hr-review-evidence")
      .getByRole("button", { name: "검색", exact: true })
      .click();
    await page.locator(".hr-review-excerpt").first().waitFor();
    assert(answerPosts === 0, "Assistant review pane sent a question");
    record(
      "Assistant review pane is separate from answer sources and normal search",
    );

    for (const [name, alter] of [
      [
        "generation-use flag changed",
        (value) => (value.used_for_generation = true),
      ],
      [
        "excerpt promoted into answer eligibility",
        (value) => (value.results[0].answer_eligible = true),
      ],
    ]) {
      const invalid = clone(reviewFixture);
      alter(invalid);
      await page.route(api + "/hr/review-evidence?**", (route) =>
        route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(invalid),
        }),
      );
      await page
        .locator(".hr-review-evidence")
        .getByRole("button", { name: "검색", exact: true })
        .click();
      await page.locator(".hr-review-error").waitFor();
      assert(
        (await page.locator(".hr-review-excerpt").count()) === 0,
        "Unsafe review response displayed",
      );
      await page.unroute(api + "/hr/review-evidence?**");
      record(name, "tampered actual review response");
    }
    await send(answerFixture);
    await page.locator(".sa-answer-part").first().waitFor();
    record(
      "Expanded answer transport accepts separately eligible current-format sources",
      "retained actual answer plus explicitly synthetic expanded-scope flags",
    );
    const citedId = answerFixture.paragraphs[0].citations[0].source_id;
    const downgradedSource = clone(
      answerFixture.sources.find((source) => source.id === citedId),
    );
    delete downgradedSource.answer_eligible;
    const sourceUrl = api + "/hr/sources/" + encodeURIComponent(citedId);
    await page.route(sourceUrl, (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(downgradedSource),
      }),
    );
    await page.locator(".sa-citations button").first().click();
    await page.locator(".sa-evidence-error").waitFor();
    assert(
      (await page.locator(".sa-source-detail .hr-original").count()) === 0,
      "Downgraded source lookup displayed",
    );
    await page.unroute(sourceUrl);
    record(
      "Current source lookup cannot lose answer-eligibility metadata",
      "tampered current source response",
    );

    await page.getByRole("button", { name: "새 대화", exact: true }).click();
    await page
      .getByRole("textbox", { name: "인사 질문", exact: true })
      .fill(heldQuestion);
    allowHeld = true;
    const heldResponse = page.waitForResponse(
      (response) =>
        response.url().endsWith("/hr/answer") &&
        response.request().method() === "POST",
    );
    await page
      .getByRole("button", { name: "인사 질문 전송", exact: true })
      .click();
    heldReceipt = await (await heldResponse).json();
    assert(
      heldReceipt.validation ===
        "NAMED_SOURCE_HELD_NO_SUBSTITUTE_OR_GENERATION" &&
        heldReceipt.status === "needs_review" &&
        heldReceipt.provider_calls?.length === 0 &&
        heldReceipt.paragraphs?.length === 0 &&
        heldReceipt.sources?.length === 0 &&
        heldReceipt.review_search_available === true,
      "Actual held document did not refuse with zero calls",
    );
    await page.locator(".sa-held-document").waitFor();
    assert(
      (await page.locator(".sa-held-document").innerText()).includes(
        "모델 호출 없이",
      ),
      "Zero-call status hidden",
    );
    assert(
      (await page.locator(".sa-answer-part,.sa-citations button").count()) ===
        0,
      "Held specialist replaced by ordinary answer",
    );
    await page
      .getByRole("button", { name: "검토 발췌 검색 열기", exact: true })
      .click();
    assert(
      (await page
        .getByRole("textbox", { name: "검토 발췌 검색어", exact: true })
        .inputValue()) === heldReceipt.held_documents[0],
      "Held document search not prefilled",
    );
    await page
      .locator(".hr-review-evidence")
      .getByRole("button", { name: "검색", exact: true })
      .click();
    await page.locator(".hr-review-excerpt").first().waitFor();
    await page.screenshot({
      path: "output/playwright/hr-expanded-held-1440.png",
      fullPage: true,
    });
    record(
      "Named-held real question refuses without provider calls and opens separate review search",
    );

    const heldContradiction = clone(heldReceipt);
    heldContradiction.provider_calls = [{ phase: "draft" }];
    await send(heldContradiction);
    await page.locator(".sa-response-error").waitFor();
    assert(
      (await page.locator(".sa-held-document").count()) === 0,
      "Contradictory no-call banner displayed",
    );
    record(
      "Contradictory named-held model-call state is blocked",
      "tampered actual held response",
    );
    for (const [name, alter] of [
      [
        "review-only source mixed into answer",
        (value) =>
          Object.assign(value.sources[0], {
            answer_eligible: false,
            review_only: true,
          }),
      ],
      [
        "expanded source missing eligibility",
        (value) => delete value.sources[0].answer_eligible,
      ],
    ]) {
      const invalid = clone(answerFixture);
      alter(invalid);
      await send(invalid);
      await page.locator(".sa-response-error").waitFor();
      assert(
        (await page.locator(".sa-answer-part,.sa-citations button").count()) ===
          0,
        "Unsafe answer rendered",
      );
      record(name, "tampered retained answer transport");
    }
    assert(
      !requests.some(
        (request) => request.path === "/api/benefits/config" || request.auth,
      ),
      "Cloud configuration probe or browser Authorization header",
    );
    assert(!errors.length, "Browser errors: " + errors.join(";"));
    return {
      status: "PASSED",
      checkedAt: new Date().toISOString(),
      upstream: "http://127.0.0.1:8846",
      capabilities: caps,
      research: ready.research,
      checks,
      widths,
      newModelGenerations: 0,
      interceptedAnswerRequests: answerPosts,
      actualHeldRequests: actualHeldPosts,
      heldDocument: {
        question: heldQuestion,
        validation: heldReceipt.validation,
        providerCalls: heldReceipt.provider_calls,
        heldDocuments: heldReceipt.held_documents,
      },
      reviewOnly: {
        answerEligible: reviewFixture.answer_eligible,
        usedForGeneration: reviewFixture.used_for_generation,
        resultCount: reviewFixture.results.length,
      },
      pageErrors: errors,
      scope:
        "UI connection and source-scope separation, not corpus approval or a retrieval/answer-quality benchmark",
    };
  } catch (error) {
    return {
      status: "FAILED",
      error: error.message,
      checks,
      widths,
      pageErrors: errors,
      interceptedAnswerRequests: answerPosts,
    };
  } finally {
    await page.unroute(api + "/hr/answer");
    await page.unroute(api + "/hr/review-evidence?**");
  }
}

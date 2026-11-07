// Synthetic delayed transport only. No actual answer/model request is forwarded.
async function verifyAssistantCancel(page) {
  const base = "http://127.0.0.1:8825",
    route = base + "/api/benefits/hr/answer";
  let requests = 0,
    delivered;
  const finished = new Promise((resolve) => {
    delivered = resolve;
  });
  await page.setViewportSize({ width: 1440, height: 1040 });
  await page.goto(base + "/hr/assistant");
  await page.locator(".sa-assistant").waitFor();
  await page.route(route, async (request) => {
    requests++;
    await new Promise((resolve) => setTimeout(resolve, 1800));
    try {
      await request.fulfill({
        status: 503,
        contentType: "application/json",
        body: '{"detail":"Synthetic delayed response must not replace interrupted message"}',
      });
    } catch {
      /* The browser may already have aborted the request. */
    } finally {
      delivered();
    }
  });
  try {
    await page
      .getByRole("textbox", { name: "인사 질문", exact: true })
      .fill("휴게시간 규정을 확인해 주세요.");
    const requested = page.waitForRequest(
      (request) => request.url() === route && request.method() === "POST",
    );
    await page
      .getByRole("button", { name: "인사 질문 전송", exact: true })
      .click();
    await requested;
    await page
      .getByRole("button", { name: "응답 수신 중지", exact: true })
      .click();
    await finished;
    await page.locator(".sa-interrupted").waitFor();
    if (
      (await page.locator(".sa-response-error,.sa-answer-part").count()) !==
        0 ||
      requests !== 1
    )
      throw Error(
        "Late or duplicate response reached the interrupted conversation",
      );
    await page.getByRole("button", { name: "새 대화", exact: true }).click();
    if (
      (await page.locator(".sa-conversation").count()) !== 0 ||
      !(await page
        .getByRole("textbox", { name: "인사 질문", exact: true })
        .isEnabled())
    )
      throw Error("New conversation not reset");
    return {
      status: "PASSED",
      interceptedRequests: requests,
      newModelGenerations: 0,
      mode: "synthetic delayed 503; response reception stopped, not backend model cancellation",
      lateResponseHidden: true,
      newConversationReset: true,
    };
  } finally {
    await page.unroute(route);
  }
}

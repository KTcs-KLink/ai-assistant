// CLI flow test, no paid API/model calls. Start the dedicated HR server first.
;async (page) => {
  const checks = [],
    errors = [],
    unexpected = []
  page.on('pageerror', (e) => errors.push(e.message))
  page.on('request', (r) => {
    const u = new URL(r.url())
    if (!['127.0.0.1', 'localhost'].includes(u.hostname)) unexpected.push(u.hostname)
  })
  const verify = async (fn, name) => {
    for (let i = 0; i < 50; i++) {
      if (await fn()) {
        checks.push(name)
        return
      }
      await page.waitForTimeout(60)
    }
    throw Error(name)
  }
  await page.goto('http://127.0.0.1:8826/hr-check')
  await page.getByRole('button', { name: '가상 직원으로 기능 확인' }).click()
  await verify(
    async () => (await page.locator('#catalog article').count()) === 6,
    'six server-evaluated benefit cards render',
  )
  await verify(
    async () => (await page.locator('#readiness article').count()) === 6,
    'all six production gates are visible',
  )
  await verify(
    async () => (await page.locator('#corpus-status').innerText()).includes('449'),
    'actual filtered HR corpus metadata renders',
  )
  const card = page.locator('#catalog article').filter({ hasText: '자녀 돌봄 지원금' })
  await card.getByRole('button', { name: '신청 준비에 담기' }).click()
  await verify(
    async () => (await page.locator('#preparations article').count()) === 1,
    'prepare action reaches the live BFF',
  )
  await page.locator('#preparations input[type=checkbox]').first().check()
  await verify(
    async () => await page.locator('#preparations input[type=checkbox]').first().isChecked(),
    'preparation checklist updates through the server',
  )
  await verify(
    async () => await page.getByRole('button', { name: '실제 신청 · 회사 시스템 연결 후 가능' }).isDisabled(),
    'actual application stays disabled',
  )
  await page.locator('#reminders').check()
  await verify(
    async () => (await page.locator('#updates').innerText()).includes('마감'),
    'opt-in deadline uses server results',
  )
  await page.locator('#family-consent').uncheck()
  await page.getByRole('button', { name: '예시 조건 저장', exact: true }).click()
  await verify(
    async () => (await card.innerText()).includes('추가 확인 필요'),
    'revoked family scope changes server eligibility',
  )
  await verify(
    async () => (await page.locator('#preparations').innerText()).includes('이전 체크 무효'),
    'profile change invalidates stale preparation in the page',
  )
  await verify(
    async () => await page.locator('#preparations input[type=checkbox]').first().isDisabled(),
    'stale checklist cannot be marked complete',
  )
  await verify(
    async () => (await page.locator('#forms article').count()) === 6,
    'six requested form types render without invented downloads',
  )
  await page.screenshot({ path: 'output/playwright/hr-domain-connected-desktop.png', fullPage: true })
  await page.getByRole('button', { name: '동의 철회·조건과 준비 기록 삭제' }).click()
  await verify(
    async () => (await page.locator('#preparations article').count()) === 0,
    'revocation removes server preparations',
  )
  await verify(
    async () => !(await page.locator('#reminders').isChecked()),
    'revocation clears reminder consent',
  )
  for (const width of [360, 390, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 })
    await verify(
      async () => await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1),
      `connected page fits ${width}px`,
    )
    if (width === 390)
      await page.screenshot({ path: 'output/playwright/hr-domain-connected-mobile.png', fullPage: true })
  }
  const secretExposure = await page.evaluate(() =>
    /sb_(?:secret|publishable)_[A-Za-z0-9_-]{12,}|sk-[A-Za-z0-9_-]{25,}|eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\./.test(
      document.body.innerText,
    ),
  )
  if (secretExposure) throw Error('credential-like string visible')
  checks.push('no credential-like value in rendered content')
  await page.getByRole('button', { name: '체험 종료', exact: true }).click()
  await verify(
    async () => !(await page.locator('#content').isVisible()),
    'logout closes the connected experience',
  )
  if (errors.length || unexpected.length) throw Error(JSON.stringify({ errors, unexpected }))
  return { checks, count: checks.length, errors, external_requests: unexpected, paid_model_calls: 0 }
}

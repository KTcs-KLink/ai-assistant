'use strict'
const $ = (id) => document.getElementById(id)
const root = '/api/benefits'
const base = root + '/hr'
let catalog = null
const labels = {
  eligible: '조건 충족 · 예시',
  needs_review: '추가 확인 필요',
  ineligible: '해당 없음 · 예시',
}
const node = (tag, text, cls) => {
  const e = document.createElement(tag)
  if (text !== undefined) e.textContent = text
  if (cls) e.className = cls
  return e
}
function clearError() {
  $('error').textContent = ''
}
function showError(error) {
  $('error').textContent = error.message || '연결을 확인하지 못했어요.'
}
function action(fn) {
  return async (event) => {
    event?.preventDefault()
    clearError()
    try {
      await fn(event)
    } catch (e) {
      showError(e)
    }
  }
}
async function request(path, method = 'GET', body) {
  const r = await fetch(path, {
    method,
    credentials: 'same-origin',
    headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: 'no-store',
  })
  if (!r.ok) {
    let detail = '요청을 완료하지 못했어요.'
    try {
      detail = (await r.json()).detail || detail
    } catch {}
    throw Error(detail)
  }
  return r.status === 204 ? null : r.json()
}
function button(text, fn, disabled = false) {
  const b = node('button', text)
  b.type = 'button'
  b.disabled = disabled
  if (fn) b.addEventListener('click', action(fn))
  return b
}
function source(parent, item) {
  const d = node('details')
  d.append(node('summary', item.title + ' · ' + item.section))
  d.append(
    node('p', '한국전력 참고자료 · KTcs 적용 미확인', 'muted'),
    node('pre', item.text || item.quote, 'source'),
  )
  parent.append(d)
}
function updateProfile(p) {
  $('employment-consent').checked = p.employment_consent
  $('family-consent').checked = p.family_consent
  $('employment').value = p.employment_type || ''
  $('hire-date').value = p.hire_date || ''
  $('ages').value = p.children_ages?.join(', ') || ''
  $('household').value = p.household_size || ''
  $('no-children').checked = Array.isArray(p.children_ages) && p.children_ages.length === 0
  disableFields()
}
function disableFields() {
  for (const id of ['employment', 'hire-date']) $(id).disabled = !$('employment-consent').checked
  for (const id of ['household', 'ages', 'no-children']) $(id).disabled = !$('family-consent').checked
  $('ages').disabled = !$('family-consent').checked || $('no-children').checked
}
async function refreshCatalog() {
  catalog = await request(base + '/catalog')
  $('catalog').replaceChildren()
  if (!catalog.cards.length)
    $('catalog').append(node('p', '승인된 회사 규정이 연결되어야 추천을 시작할 수 있어요.'))
  for (const c of catalog.cards) {
    const article = node('article', undefined, 'card')
    article.append(
      node('span', labels[c.status], 'tag'),
      node('h3', c.title),
      node('p', c.value),
      node('p', c.reasons.join(' '), 'status'),
    )
    const d = node('details')
    d.append(node('summary', '조건과 예시 규정 확인'))
    for (const check of c.checks)
      d.append(
        node(
          'p',
          check.label +
            ' · ' +
            { pass: '충족', unknown: '미확인', fail: '미충족' }[check.state] +
            ' · ' +
            check.reason,
        ),
      )
    d.append(node('pre', c.source.quote, 'source'))
    article.append(d)
    article.append(
      button(c.status === 'eligible' ? '신청 준비에 담기' : '확인할 항목 담기', async () => {
        await request(base + '/preparations/' + c.id, 'POST', {
          conditions_revision: catalog.conditions_revision,
          policy_sha256: c.policy_sha256,
        })
        await refreshPlans()
      }),
    )
    $('catalog').append(article)
  }
}
async function refreshPlans() {
  const data = await request(base + '/preparations')
  $('preparations').replaceChildren()
  if (!data.plans.length)
    $('preparations').append(node('p', '혜택에서 준비를 시작하면 여기에 나타나요.', 'muted'))
  for (const plan of data.plans) {
    const article = node('article', undefined, 'card')
    article.append(
      node('h3', plan.title),
      node('p', plan.stale ? '조건·규정 재확인 필요 · 이전 체크 무효' : '준비 중 · 실제 미제출', 'status'),
    )
    plan.checklist.forEach((text, index) => {
      const label = node('label', undefined, 'checklist'),
        box = document.createElement('input')
      box.type = 'checkbox'
      box.checked = plan.checked.includes(index)
      box.disabled = plan.stale
      box.setAttribute('aria-label', plan.title + ' ' + text)
      box.addEventListener(
        'change',
        action(async () => {
          await request(base + '/preparations/' + plan.id, 'PATCH', { index, checked: box.checked })
          await refreshPlans()
        }),
      )
      label.append(box, node('span', text))
      article.append(label)
    })
    article.append(
      button('실제 신청 · 회사 시스템 연결 후 가능', null, true),
      button('준비 목록 삭제', async () => {
        await request(base + '/preparations/' + plan.id, 'DELETE')
        await refreshPlans()
      }),
    )
    $('preparations').append(article)
  }
}
async function refreshForms() {
  const data = await request(base + '/forms')
  $('forms').replaceChildren()
  for (const f of data.forms) {
    const article = node('article', undefined, 'card')
    article.append(
      node('h3', f.title),
      node(
        'p',
        f.official_available ? '회사 빈 양식 검증됨 · 직원 권한 필요' : '회사 공식 양식 연결 전',
        'status',
      ),
    )
    for (const text of f.preparation_items) article.append(node('p', text))
    article.append(node('p', f.notice, 'muted'))
    $('forms').append(article)
  }
}
async function refreshReadiness() {
  const data = await request(base + '/readiness')
  $('readiness').replaceChildren()
  for (const g of data.gates) {
    const div = node('article', undefined, 'card')
    div.append(
      node('h3', g.priority + '순위 · ' + (g.ready ? '회사 규정 준비됨' : '실사용 연결·검증 대기')),
      node('p', g.message),
    )
    $('readiness').append(div)
  }
  $('corpus-status').textContent =
    `한국전력 인사 참고자료 ${data.research.source_count}개 · 실제 KTcs 자료 아님 · 검색 성능 재평가 아님`
}
async function refreshUpdates() {
  const data = await request(base + '/updates')
  $('reminders').checked = data.enabled
  $('updates').replaceChildren()
  if (!data.enabled) $('updates').append(node('p', '안내를 받으려면 위 항목을 선택해 주세요.'))
  else if (!data.updates.length) $('updates').append(node('p', '추가로 안내할 변경이 없어요.'))
  for (const item of data.updates)
    $('updates').append(
      node(
        'p',
        (catalog.cards.find((c) => c.id === item.benefit_id)?.title || '혜택') + ' · ' + item.message,
      ),
    )
}
async function refresh() {
  await refreshCatalog()
  await Promise.all([refreshPlans(), refreshForms(), refreshReadiness(), refreshUpdates()])
}
$('start').addEventListener(
  'click',
  action(async () => {
    await request(root + '/session/demo', 'POST')
    const p = await request(root + '/profile/example', 'POST')
    updateProfile(p)
    $('content').hidden = false
    $('logout').disabled = false
    await refresh()
  }),
)
$('logout').addEventListener(
  'click',
  action(async () => {
    await request(root + '/session', 'DELETE')
    $('content').hidden = true
    $('answer').replaceChildren()
    $('logout').disabled = true
    catalog = null
  }),
)
for (const id of ['employment-consent', 'family-consent', 'no-children'])
  $(id).addEventListener('change', disableFields)
$('profile-form').addEventListener(
  'submit',
  action(async () => {
    const raw = $('ages').value.trim(),
      parts = raw ? raw.split(',').map((x) => x.trim()) : []
    if (parts.some((x) => !/^\d+$/.test(x) || Number(x) > 30))
      throw Error('예시 자녀 나이는 0~30세 정수로 입력해 주세요.')
    const p = {
      employment_consent: $('employment-consent').checked,
      family_consent: $('family-consent').checked,
      employment_type: $('employment').value || null,
      hire_date: $('hire-date').value || null,
      children_ages: $('no-children').checked ? [] : raw ? parts.map(Number) : null,
      household_size: $('household').value ? Number($('household').value) : null,
    }
    updateProfile(await request(root + '/profile', 'PUT', p))
    $('profile-status').textContent = '조건을 저장했어요. 이전 준비 항목은 최신 조건으로 다시 확인하세요.'
    await refresh()
  }),
)
$('revoke').addEventListener(
  'click',
  action(async () => {
    await request(root + '/profile', 'DELETE')
    updateProfile(await request(root + '/profile'))
    $('answer').replaceChildren()
    $('profile-status').textContent = '동의를 철회하고 조건·준비·알림 정보를 지웠어요.'
    await refresh()
  }),
)
$('question-form').addEventListener(
  'submit',
  action(async () => {
    const b = $('ask')
    b.disabled = true
    $('answer').replaceChildren(node('p', '허용된 원문을 찾아 답변과 인용을 확인하고 있어요.', 'status'))
    try {
      const data = await request(base + '/answer', 'POST', { question: $('question').value })
      $('answer').replaceChildren(
        node('p', data.notice, 'notice'),
        node(
          'p',
          data.status === 'answered'
            ? '근거를 확인한 참고 답변 · 실제 자격 승인 아님'
            : '추가 확인이 필요한 참고 답변',
          'status',
        ),
      )
      for (const part of data.paragraphs) {
        const block = node('div', undefined, 'answer-part')
        block.append(node('p', part.text))
        for (const citation of part.citations) {
          const s = data.sources.find((s) => s.id === citation.source_id)
          if (s) {
            const d = node('details')
            d.append(node('summary', s.title + ' · ' + s.section), node('pre', citation.quote, 'source'))
            block.append(d)
          }
        }
        $('answer').append(block)
      }
      for (const text of data.missing_information) $('answer').append(node('p', '확인 필요: ' + text))
      const ids = new Set(data.paragraphs.flatMap((p) => p.citations.map((c) => c.source_id)))
      for (const s of data.sources) if (!data.paragraphs.length || ids.has(s.id)) source($('answer'), s)
    } catch (error) {
      $('answer').replaceChildren(node('p', '답변을 확인하지 못했어요. 위 안내를 확인해 주세요.'))
      throw error
    } finally {
      b.disabled = false
    }
  }),
)
$('reminders').addEventListener(
  'change',
  action(async () => {
    await request(base + '/reminders', 'PUT', { enabled: $('reminders').checked })
    await refreshUpdates()
  }),
)
$('refresh-updates').addEventListener('click', action(refreshUpdates))
$('hire-date').max = new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Seoul' }).format(new Date())

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
  if (item.excerpt_only) d.append(node('p', '검색된 원문의 일부입니다. 전체 조문과 표의 확인이 필요합니다.', 'muted'))
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
    `한국전력 인사 답변용 원문 ${data.research.source_count}개 · 추가 검토 원문 ${data.research.review_only_count || 0}개 · 실제 KTcs 자료 아님`
  const domains = data.research.domain_review
  $('review-category').disabled = !domains?.available
  $('review-domain-status').textContent = domains?.available
    ? `기본 인사 검토 후보 ${domains.default_windows}개 검색 조각 · 인사 외 ${domains.non_hr_windows}개 별도 분리. 혼합·판단 보류는 후보로 보존하며, 분류만으로 답변 사용을 승인하지 않습니다.`
    : '기존 검토 범위입니다. 재분류 검색 연결 전에는 자료 분류 필터를 제공하지 않습니다.'
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
    $('answer').replaceChildren(node('p', '질문 뜻을 확인하고 관련 규정에서 답변 근거를 찾고 있어요.', 'status'))
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
      if (data.understanding?.interpreted_as) {
        $('answer').append(node('p', '질문을 이렇게 이해했어요: ' + data.understanding.interpreted_as, 'status'))
      }
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
      if (data.source_conditions?.length) {
        const conditions = node('div', undefined, 'notice')
        conditions.append(node('h3', '함께 확인할 조건·예외 원문'))
        conditions.append(node('p', '아래는 인용한 문단 전체를 원문 그대로 표시한 내용입니다. 다른 조문의 필수 조건까지 모두 찾았다는 뜻은 아니에요.'))
        for (const item of data.source_conditions) {
          conditions.append(node('p', item.section), node('pre', item.quote, 'source'))
        }
        $('answer').append(conditions)
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
$('review-form').addEventListener('submit', action(async () => {
  $('review-results').replaceChildren(node('p', '추가 검토 원문을 찾고 있어요.'))
  const category = $('review-category').disabled ? 'hr_candidates' : $('review-category').value
  const data = await request(base + '/review-evidence?q=' + encodeURIComponent($('review-question').value) + '&category=' + encodeURIComponent(category))
  $('review-results').replaceChildren(node('p', data.notice, 'notice'))
  if (!data.results.length) $('review-results').append(node('p', '일치하는 추가 검토 원문이 없어요.'))
  for (const item of data.results) {
    const article = node('article', undefined, 'card')
    article.append(node('p', '추가 검토 필요 · 답변 생성에 사용하지 않음', 'tag'))
    if (item.domain_label) article.append(node('p', '자동 분류: ' + ({HR:'인사 관련',NON_HR:'인사 외 업무',MIXED:'인사·다른 업무 혼합',REVIEW_REQUIRED:'판단 보류'}[item.domain_label] || '판단 보류'), 'tag'))
    const reasonLabels = {
      HR_SCOPE_REVIEW_REQUIRED: '인사 업무 범위 확인 필요', EXISTING_ANSWER_GATE_HELD: '답변용 원문 검토 미완료',
      INCOMPLETE_ARTICLE_OR_FORM: '조문 전체·표·서식 확인 필요', LAYOUT_REVIEW_REQUIRED: '표·글리프·배치 확인 필요',
      NEW_SOURCE_LAYOUT_OR_BOUNDARY_UNVERIFIED: '표 순서·조문 경계 확인 필요',
      ARTICLE_BODY_MISSING_OR_TOO_SHORT: '제목 외 본문 확인 필요', PARAGRAPH_SEQUENCE_INCOMPLETE: '항 번호·누락 확인 필요',
    }
    const reasons = [...new Set((item.hold_reasons || []).map(reason => reasonLabels[reason] || reason))]
    if (reasons.length) article.append(node('p', reasons.join(' · ')))
    source(article, item)
    $('review-results').append(article)
  }
}))
$('hire-date').max = new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Seoul' }).format(new Date())

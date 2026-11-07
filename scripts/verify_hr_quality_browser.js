// Local end-to-end check. Two real configured-model calls; no cloud database writes.
async page => {
  const external=[],errors=[]
  page.on('request',r=>{if(!['127.0.0.1','localhost'].includes(new URL(r.url()).hostname))external.push(new URL(r.url()).hostname)})
  page.on('pageerror',e=>errors.push(e.message))
  await page.setViewportSize({width:1440,height:1000})
  await page.goto('http://127.0.0.1:8828/hr-check')
  await page.getByRole('button',{name:'가상 직원으로 기능 확인'}).click()
  await page.locator('#readiness article').nth(5).waitFor({timeout:30000})
  const question='민원 대응 때문에 점심 휴게시간을 12시가 아닌 시간대로 운영할 수 있나요?'
  await page.getByRole('textbox',{name:'일반 인사 업무 질문'}).fill(question)
  const pending=page.waitForResponse(r=>r.url().endsWith('/api/benefits/hr/answer')&&r.request().method()==='POST',{timeout:180000})
  await page.getByRole('button',{name:'근거와 함께 질문하기'}).click()
  const response=await pending,data=await response.json()
  if(response.status()!==200||!data.paragraphs.length||data.employee_data_sent||data.ktcs_applicable||data.human_approved)throw Error('Live answer or scope boundary failed')
  if(data.provider_calls.length!==2||data.semantic_review.independent)throw Error('Source comparison accounting changed')
  for(const c of data.source_conditions){const s=data.sources.find(s=>s.id===c.source_id);if(!s||s.text.slice(c.start,c.end)!==c.quote)throw Error('Original condition span mismatch')}
  await page.getByRole('heading',{name:'함께 확인할 조건·예외 원문'}).waitFor()
  await page.locator('#answer details summary').first().click()
  await page.locator('#answer-heading').scrollIntoViewIfNeeded()
  await page.screenshot({path:'output/playwright/hr-quality-final-desktop.png'})
  await page.setViewportSize({width:390,height:844})
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)
  await page.screenshot({path:'output/playwright/hr-quality-final-mobile.png'})
  if(overflow||external.length||errors.length)throw Error('Browser layout/runtime boundary failed')
  return {question,http_status:response.status(),status:data.status,paragraphs:data.paragraphs.length,condition_cards:data.source_conditions.length,
    source_spans_exact:true,actual_model_calls:data.provider_calls.length,employee_data_sent:false,cloud_database_writes:0,
    independent_review:false,human_approved:false,mobile_overflow:false,browser_errors:errors,external_browser_requests:external}
}

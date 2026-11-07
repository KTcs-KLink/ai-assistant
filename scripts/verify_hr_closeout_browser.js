async page => {
  const failures=[],external=[]
  page.on('pageerror',e=>failures.push(e.message))
  page.on('request',r=>{if(!['127.0.0.1','localhost'].includes(new URL(r.url()).hostname))external.push(new URL(r.url()).hostname)})
  await page.goto('http://127.0.0.1:8842/hr-check')
  await page.getByRole('button',{name:'가상 직원으로 기능 확인'}).click()
  await page.locator('#readiness article').nth(5).waitFor({timeout:30000})
  const question='육아휴직을 6개월 하는 경우와 출산휴가 뒤 육아휴직을 3개월 하는 경우에 결원을 보충할 수 있나요?'
  await page.getByRole('textbox',{name:'일반 인사 업무 질문'}).fill(question)
  const pending=page.waitForResponse(r=>r.url().endsWith('/api/benefits/hr/answer')&&r.request().method()==='POST',{timeout:180000})
  await page.getByRole('button',{name:'근거와 함께 질문하기'}).click()
  const response=await pending,data=await response.json()
  if(response.status()!==200||!data.paragraphs.length||data.employee_data_sent||data.ktcs_applicable||data.human_approved)throw Error('Live answer or scope boundary failed')
  if(data.retrieval.method!=='hr_bge_m3_hybrid'||data.quote_method!=='APPLICATION_RECONSTRUCTED_ORIGINAL_SPANS_NO_GENERATED_QUOTES')throw Error('Old retrieval or generated quote path remains')
  for(const p of data.paragraphs)for(const c of p.citations){const s=data.sources.find(s=>s.id===c.source_id);if(!s||!s.text.includes(c.quote))throw Error('Citation is not an actual original span')}
  for(const c of data.source_conditions){const s=data.sources.find(s=>s.id===c.source_id);if(!s||s.text.slice(c.start,c.end)!==c.quote)throw Error('Condition range mismatch')}
  await page.locator('#answer .answer-part').first().waitFor()
  await page.locator('#answer details summary').first().click()
  await page.locator('#answer-heading').scrollIntoViewIfNeeded()
  await page.screenshot({path:'output/playwright/hr-closeout-desktop.png'})
  await page.setViewportSize({width:390,height:844})
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)
  await page.screenshot({path:'output/playwright/hr-closeout-mobile.png'})
  if(overflow||external.length||failures.length)throw Error('Browser flow or layout failed')
  return {question,http_status:response.status(),status:data.status,paragraphs:data.paragraphs.map(p=>p.text),
    retrieval:data.retrieval.method,quote_method:data.quote_method,quotes_and_condition_spans_exact:true,
    actual_model_calls:data.provider_calls.length,employee_data_sent:false,cloud_database_writes:0,
    human_approved:false,mobile_overflow:false,browser_errors:failures,external_browser_requests:external}
}

async page => {
  const errors=[],external=[],payloads=[]
  page.on('pageerror',e=>errors.push(e.message))
  page.on('request',r=>{
    if(!['127.0.0.1','localhost'].includes(new URL(r.url()).hostname))external.push(new URL(r.url()).hostname)
    if(r.url().endsWith('/api/benefits/hr/answer'))payloads.push(Object.keys(JSON.parse(r.postData()||'{}')))
  })
  await page.setViewportSize({width:1280,height:1000})
  await page.goto('http://127.0.0.1:8846/hr-check')
  const capabilities=await (await page.request.get('http://127.0.0.1:8846/api/benefits/hr/capabilities')).json()
  if(capabilities.source_scope!=='expanded')throw Error('Wrong source scope')
  await page.getByRole('button',{name:'가상 직원으로 기능 확인'}).click()
  await page.locator('#readiness article').nth(5).waitFor({timeout:60000})
  if(!(await page.locator('#corpus-status').textContent()).includes('528'))throw Error('Expanded count not shown')
  await page.getByText('추가 검토가 필요한 원문 검색',{exact:true}).click()
  await page.getByRole('textbox',{name:'추가 검토 원문 검색어'}).fill('별정직 채용 구비서류')
  const pendingReview=page.waitForResponse(r=>r.url().includes('/hr/review-evidence?'),{timeout:60000})
  await page.getByRole('button',{name:'추가 검토 원문 찾기'}).click()
  const review=await (await pendingReview).json()
  if(!review.results?.length||review.used_for_generation!==false||review.results.some(r=>r.answer_eligible||!r.review_only))throw Error('Review boundary failed')
  await page.locator('#review-results .card').first().waitFor()
  const results=[]
  for(const question of ['월급은 매달 며칠 들어오나요?','상임임원 복무규정의 적용 대상과 적용 범위는 어떻게 되나요?']){
    await page.getByRole('textbox',{name:'일반 인사 업무 질문'}).fill(question)
    const pending=page.waitForResponse(r=>r.url().endsWith('/hr/answer')&&r.request().method()==='POST',{timeout:180000})
    await page.getByRole('button',{name:'근거와 함께 질문하기'}).click()
    const response=await pending,data=await response.json()
    if(response.status()!==200||!data.paragraphs?.length)throw Error('Live answer unavailable: '+(data.validation||response.status()))
    if(data.retrieval.source_count!==528)throw Error('Answer did not use expanded scope')
    for(const p of data.paragraphs)for(const c of p.citations){
      const s=data.sources.find(s=>s.id===c.source_id)
      if(!s||!s.text.includes(c.quote)||s.review_only||!s.answer_eligible)throw Error('Citation escaped verified answer sources')
    }
    results.push({question,status:data.status,body:data.paragraphs.map(p=>p.text),
      cited_sources:[...new Set(data.paragraphs.flatMap(p=>p.citations.map(c=>c.source_id)))],
      missing:data.missing_information,actual_generation_requests:data.provider_calls.length,model:data.model})
    await page.evaluate(value=>{ window.klinkSourceExpansionCheck=value },results)
  }
  if(!results[1].cited_sources.some(id=>['HF-b0eb39db072911bde29eccee2a99','HF-2249bcd5ffcf63e6da30e1630f5d'].includes(id)))throw Error('New executive source was not used')
  await page.locator('#answer').screenshot({path:'output/playwright/hr-source-expansion.png'})
  await page.getByRole('textbox',{name:'일반 인사 업무 질문'}).fill('단시간근로자 운영지침의 근무시간은 어떻게 되나요?')
  const heldPending=page.waitForResponse(r=>r.url().endsWith('/hr/answer')&&r.request().method()==='POST',{timeout:60000})
  await page.getByRole('button',{name:'근거와 함께 질문하기'}).click()
  const held=await (await heldPending).json()
  if(held.validation!=='NAMED_SOURCE_HELD_NO_SUBSTITUTE_OR_GENERATION'||held.paragraphs.length||held.provider_calls.length)throw Error('Held specialist document was substituted')
  await page.setViewportSize({width:390,height:844})
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)
  if(overflow||errors.length||external.length||payloads.some(keys=>keys.join(',')!=='question'))throw Error('Browser/privacy failure')
  return {results,source_scope:'expanded',answer_units:528,review_only_units:3334,review_search_results:review.results.length,
    held_named_document_withheld_without_model_call:true,
    quotes_exact:true,review_sources_not_used_for_answers:true,employee_profile_sent:false,external_browser_requests:external,
    browser_errors:errors,mobile_overflow:false,supabase_ingestion:'HOLD',human_approved:false,ktcs_applicable:false}
}

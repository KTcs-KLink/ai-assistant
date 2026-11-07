async page => {
  const errors=[],external=[],payloads=[]
  page.on('pageerror',e=>errors.push(e.message))
  page.on('request',r=>{
    if(!['127.0.0.1','localhost'].includes(new URL(r.url()).hostname))external.push(new URL(r.url()).hostname)
    if(r.url().endsWith('/api/benefits/hr/answer'))payloads.push(Object.keys(JSON.parse(r.postData()||'{}')))
  })
  await page.setViewportSize({width:1280,height:1000})
  await page.goto('http://127.0.0.1:8844/hr-check')
  await page.getByRole('button',{name:'가상 직원으로 기능 확인'}).click()
  await page.locator('#readiness article').nth(5).waitFor({timeout:30000})
  const results=[]
  for(const question of ['월급은 매달 며칠 들어오나요?','회사에서 주는 돈이 통장에 들어오는 날은 언제예요?']){
    await page.getByRole('textbox',{name:'일반 인사 업무 질문'}).fill(question)
    const pending=page.waitForResponse(r=>r.url().endsWith('/api/benefits/hr/answer')&&r.request().method()==='POST',{timeout:180000})
    await page.getByRole('button',{name:'근거와 함께 질문하기'}).click()
    const response=await pending,data=await response.json()
    if(response.status()!==200||!data.paragraphs?.length)throw Error('Live answer unavailable')
    if(data.understanding?.intents.join(',')!=='regular_payday')throw Error('Intent changed across wording')
    if(data.answer_method!=='SOURCE_EXTRACTED_FACTS'||data.provider_calls.length!==1)throw Error('Actual source extraction accounting failed')
    for(const p of data.paragraphs)for(const c of p.citations){const s=data.sources.find(s=>s.id===c.source_id);if(!s||!s.text.includes(c.quote))throw Error('Non-original citation')}
    await page.getByText('질문을 이렇게 이해했어요: 정기 급여 지급일',{exact:true}).waitFor()
    results.push({question,intent:data.understanding.intents,body:data.paragraphs.map(p=>p.text),sources:data.paragraphs.flatMap(p=>p.citations.map(c=>c.source_id)),actual_model_calls:data.provider_calls.length})
  }
  if(JSON.stringify(results[0].body)!==JSON.stringify(results[1].body)||JSON.stringify(results[0].sources)!==JSON.stringify(results[1].sources))throw Error('Equivalent questions changed core fact/source')
  await page.locator('#answer details summary').first().click()
  await page.locator('#answer').screenshot({path:'output/playwright/hr-intent-equivalent.png'})
  await page.setViewportSize({width:390,height:844})
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)
  if(overflow||errors.length||external.length||payloads.some(keys=>keys.join(',')!=='question'))throw Error('Browser/privacy boundary failed')
  return {results,same_core_answer_and_source:true,meaning_visible:true,quotes_exact:true,employee_profile_sent:false,
    mobile_overflow:false,errors,external_requests:external,supabase_ingestion:'HOLD',human_approved:false}
}

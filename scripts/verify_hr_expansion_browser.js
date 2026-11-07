async page => {
  const external=[],errors=[]
  page.on('request',r=>{const host=new URL(r.url()).hostname;if(!['127.0.0.1','localhost'].includes(host))external.push(host)})
  page.on('pageerror',e=>errors.push(e.message))
  const results=[]
  const questions=[
    '단시간근로자가 소정근로시간을 초과하여 근무하려면 어떤 동의가 필요한가요?',
    '임직원 겸직 관련 행동기준 제9조의 겸직현황 조사는 언제 어떤 기준으로 하나요?'
  ]
  for(const question of questions){
    await page.getByRole('textbox',{name:'일반 인사 업무 질문'}).fill(question)
    const pending=page.waitForResponse(r=>r.url().endsWith('/api/benefits/hr/answer')&&r.request().method()==='POST',{timeout:180000})
    await page.getByRole('button',{name:'근거와 함께 질문하기'}).click()
    const response=await pending,data=await response.json()
    if(response.status()!==200||!data.paragraphs.length||data.employee_data_sent||data.ktcs_applicable||data.human_approved)throw Error('Live answer or scope failure')
    if(data.retrieval.source_count!==873||data.retrieval.newly_reviewed_source_count!==289)throw Error('Unexpected corpus version')
    if(!data.sources.every(s=>s.original_text_layer_verified))throw Error('An unrechecked source reached the UI')
    for(const paragraph of data.paragraphs)for(const cite of paragraph.citations){
      const s=data.sources.find(s=>s.id===cite.source_id)
      if(!s||!s.text.includes(cite.quote))throw Error('Not an exact original quote')
    }
    for(const c of data.source_conditions){const s=data.sources.find(s=>s.id===c.source_id);if(!s||s.text.slice(c.start,c.end)!==c.quote)throw Error('Condition offset mismatch')}
    if(question.includes('겸직현황')&&!data.sources.some(s=>s.review_origin==='local_original_source_review'))throw Error('Newly reviewed source was not connected')
    await page.locator('#answer .answer-part').first().waitFor()
    results.push({question,status:data.status,paragraphs:data.paragraphs.length,actual_provider_calls:data.provider_calls.length,exact_quotes:true,source_count:data.retrieval.source_count})
  }
  await page.locator('#answer details summary').first().click()
  await page.locator('#answer-heading').scrollIntoViewIfNeeded()
  await page.screenshot({path:'output/playwright/hr-expansion-desktop.png'})
  await page.setViewportSize({width:390,height:844})
  if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Mobile overflow')
  const question='안전보건관리규정의 안전보건교육은 누가 시행하나요?'
  await page.getByRole('textbox',{name:'일반 인사 업무 질문'}).fill(question)
  const pending=page.waitForResponse(r=>r.url().endsWith('/api/benefits/hr/answer')&&r.request().method()==='POST',{timeout:90000})
  await page.getByRole('button',{name:'근거와 함께 질문하기'}).click()
  const boundary=await (await pending).json()
  if(boundary.validation!=='AMBIGUOUS_SOURCE_VERSION_NO_GENERATION'||boundary.paragraphs.length)throw Error('Unselected document versions were mixed')
  await page.locator('#answer-heading').evaluate(el=>el.scrollIntoView({block:'start'}))
  await page.screenshot({path:'output/playwright/hr-expansion-mobile.png'})
  if(external.length||errors.length)throw Error('Browser errors or external browser requests')
  return {results,ambiguous_versions_withheld_before_gpt:true,external_browser_requests:external,browser_errors:errors,mobile_overflow:false,cloud_database_writes:0,company:'KEPCO',human_approved:false}
}

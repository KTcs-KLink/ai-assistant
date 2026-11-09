async page => {
  const errors=[],external=[],answers=[]
  page.on('pageerror',e=>errors.push(e.message))
  page.on('request',r=>{
    if(!['127.0.0.1','localhost'].includes(new URL(r.url()).hostname))external.push(new URL(r.url()).hostname)
    if(r.url().endsWith('/hr/answer'))answers.push(r.method())
  })
  await page.setViewportSize({width:1280,height:1000})
  await page.goto('http://127.0.0.1:8846/hr-check')
  const capabilities=await (await page.request.get('http://127.0.0.1:8846/api/benefits/hr/capabilities')).json()
  if(capabilities.review_domains!=='reclassified')throw Error('Wrong classification version')
  await page.getByRole('button',{name:'가상 직원으로 기능 확인'}).click()
  await page.locator('#readiness article').nth(5).waitFor({timeout:60000})
  const state=await (await page.request.get('http://127.0.0.1:8846/api/benefits/hr/readiness')).json()
  if(state.research.source_count!==528||!state.research.domain_review?.available)throw Error('Answer scope changed or separation unavailable')
  await page.getByText('추가 검토가 필요한 원문 검색',{exact:true}).click()
  const results=[]
  for(const [category,q] of [['hr_candidates','계약'],['non_hr','계약'],['hr','휴가'],['mixed','교육'],['needs_review','부칙']]){
    await page.getByRole('combobox',{name:'검토 자료 분류'}).selectOption(category)
    await page.getByRole('textbox',{name:'추가 검토 원문 검색어'}).fill(q)
    const pending=page.waitForResponse(r=>r.url().includes('/hr/review-evidence?'),{timeout:30000})
    await page.getByRole('button',{name:'추가 검토 원문 찾기'}).click()
    const response=await pending,data=await response.json()
    if(response.status()!==200||!data.domain_separation_enabled||data.domain_filter!==category||data.used_for_generation!==false)throw Error('Invalid domain response')
    if(!data.results.length)throw Error('Expected actual classified source results: '+category)
    if(data.results.some(r=>r.answer_eligible||!r.review_only||r.human_approved))throw Error('Classification promoted source approval')
    const labels=data.results.map(r=>r.domain_label)
    if(category==='hr_candidates'&&labels.includes('NON_HR'))throw Error('Non-HR leaked into default candidates')
    const only={non_hr:'NON_HR',hr:'HR',mixed:'MIXED',needs_review:'REVIEW_REQUIRED'}[category]
    if(only&&labels.some(label=>label!==only))throw Error('Cross-category source leak')
    results.push({category,count:data.results.length,labels,window_ids:data.results.map(r=>r.window_id)})
  }
  const defaults=new Set(results[0].window_ids)
  if(results[1].window_ids.some(id=>defaults.has(id)))throw Error('Non-HR window appears in default results')
  await page.getByRole('combobox',{name:'검토 자료 분류'}).selectOption('non_hr')
  await page.getByRole('textbox',{name:'추가 검토 원문 검색어'}).fill('계약')
  const last=page.waitForResponse(r=>r.url().includes('/hr/review-evidence?'))
  await page.getByRole('button',{name:'추가 검토 원문 찾기'}).click()
  await last
  await page.getByText('자동 분류: 인사 외 업무',{exact:true}).first().waitFor()
  await page.locator('details:has(#review-form)').screenshot({path:'output/playwright/hr-reclassification-separated.png'})
  await page.setViewportSize({width:390,height:844})
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)
  if(overflow||errors.length||external.length||answers.length)throw Error('Browser, privacy, or no-generation boundary failed')
  return {results,default_excludes_non_hr:true,separate_non_hr_search:true,answer_source_units:state.research.source_count,
    domain_counts:state.research.domain_review.window_counts,model_answer_requests:0,external_requests:external,browser_errors:errors,
    mobile_overflow:false,supabase_ingestion:'HOLD',human_approved:false,ktcs_applicable:false}
}

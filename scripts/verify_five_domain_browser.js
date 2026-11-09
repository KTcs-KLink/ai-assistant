async page => {
  const errors=[],external=[],modelRequests=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('request',r=>{
    const u=new URL(r.url());
    if(['http:','https:'].includes(u.protocol)&&!['127.0.0.1','localhost'].includes(u.hostname))external.push(u.hostname);
    if(u.pathname.includes('/answer')||u.hostname.includes('openai.com'))modelRequests.push(u.pathname);
  });
  await page.setViewportSize({width:1280,height:1000});
  await page.goto('http://127.0.0.1:8852/');
  await page.locator('#rows .entry').first().waitFor();
  if(await page.locator('#total-count').innerText()!=='10,205')throw Error('Missing full source coverage');
  if(await page.locator('#window-count').innerText()!=='8,511')throw Error('Existing vectors changed');
  if(await page.locator('#workflow-count').innerText()!=='34')throw Error('Original workflows changed');
  const selectors=await page.evaluate(()=>({
    domains:[...document.querySelectorAll('#domain-filter option')].map(o=>o.value).filter(Boolean),
    tasks:[...document.querySelectorAll('#workflow-filter option')].map(o=>o.value).filter(Boolean),
    expected:JSON.parse(document.getElementById('report-data').textContent).taxonomy.tasks.map(t=>t.code)
  }));
  if(JSON.stringify(selectors.domains)!==JSON.stringify(['01','02','03','04','05']))throw Error('Only five domains permitted');
  if(JSON.stringify(selectors.tasks)!==JSON.stringify(selectors.expected)||selectors.tasks.length!==34)throw Error('Only original 34 workflows permitted');
  const domainResults=[];
  for(const code of selectors.domains){
    await page.getByRole('combobox',{name:'도메인',exact:true}).selectOption(code);
    const state=await page.evaluate(code=>{
      const data=JSON.parse(document.getElementById('report-data').textContent);
      return {code,expected:data.summary.primary_domain_counts[code]||0,
        actualText:document.getElementById('result-count').textContent,
        invalid:[...document.querySelectorAll('#rows .entry')].some(e=>e.dataset.domain!==code)};
    },code);
    if(state.invalid||!state.actualText.startsWith(state.expected.toLocaleString('ko-KR')+'개'))throw Error('Domain filter mismatch '+code);
    domainResults.push(state);
  }
  await page.getByRole('combobox',{name:'도메인',exact:true}).selectOption('02');
  await page.getByRole('combobox',{name:'업무',exact:true}).selectOption('02.07');
  if(await page.locator('#rows .entry').evaluateAll(rows=>!rows.length||rows.some(r=>r.dataset.primary!=='02.07')))throw Error('Workflow filter mismatch');
  await page.locator('#rows .entry summary').first().click();
  if(!await page.locator('#rows .entry .preview').first().innerText())throw Error('Public source preview missing');
  await page.getByLabel('해당 도메인·업무의 복수 직접 연결도 포함').check();
  const multiple=await page.evaluate(()=>{
    const d=JSON.parse(document.getElementById('report-data').textContent);
    return {expected:d.records.filter(r=>r.scope_decision==='IN_SCOPE'&&r.direct_paths.includes('02.07')).length,
      actualText:document.getElementById('result-count').textContent};
  });
  if(!multiple.actualText.startsWith(multiple.expected.toLocaleString('ko-KR')+'개'))throw Error('Direct multi-link filter mismatch');
  await page.getByLabel('해당 도메인·업무의 복수 직접 연결도 포함').uncheck();
  await page.getByRole('combobox',{name:'도메인',exact:true}).selectOption('01');
  await page.getByRole('combobox',{name:'업무',exact:true}).selectOption('01.05');
  await page.getByRole('searchbox').fill('휴가');
  if(!await page.locator('#rows .entry').count())throw Error('Actual HR query not found');
  await page.getByRole('searchbox').fill('');
  const scopeResults=[];
  for(const key of ['ADJACENT_SCOPE','OUTSIDE_SCOPE','REVIEW_REQUIRED','PRIVACY_HOLD']){
    await page.getByRole('combobox',{name:'자료 구분',exact:true}).selectOption(key);
    if(key==='ADJACENT_SCOPE')await page.getByRole('combobox',{name:'도메인',exact:true}).selectOption('');
    const state=await page.evaluate(key=>{
      const data=JSON.parse(document.getElementById('report-data').textContent);
      return {key,expected:data.summary.scope_counts[key],actualText:document.getElementById('result-count').textContent,
        invalid:[...document.querySelectorAll('#rows .entry')].some(e=>e.dataset.scope!==key||e.dataset.primary),
        workflowDisabled:document.getElementById('workflow-filter').disabled};
    },key);
    if(state.invalid||!state.workflowDisabled||!state.actualText.startsWith(state.expected.toLocaleString('ko-KR')+'개'))throw Error('Scope filter mismatch '+key);
    scopeResults.push(state);
  }
  const privacy=await page.evaluate(()=>{
    const data=JSON.parse(document.getElementById('report-data').textContent);
    const held=data.records.filter(r=>r.privacy_hold);
    return {held:held.length,exposed:held.some(r=>r.preview||r.links.length||r.direct_paths.length)};
  });
  if(privacy.held!==11||privacy.exposed)throw Error('Private source export boundary failed');
  await page.getByRole('combobox',{name:'자료 구분',exact:true}).selectOption('');
  if(!(await page.locator('#result-count').innerText()).startsWith('10,205개'))throw Error('All retained data not accessible');
  await page.getByRole('combobox',{name:'자료 구분',exact:true}).selectOption('IN_SCOPE');
  await page.getByRole('combobox',{name:'도메인',exact:true}).selectOption('01');
  await page.screenshot({path:'output/playwright/five-domain-scope.png'});
  await page.setViewportSize({width:390,height:844});
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
  if(overflow||errors.length||external.length||modelRequests.length)throw Error('Browser or no-generation boundary failed');
  return {taxonomy_domains:5,taxonomy_workflows:34,domain_filters:domainResults,scope_filters:scopeResults,
    workflow_filter:true,multiple_direct_memberships:multiple,source_units:10205,existing_vector_windows:8511,
    privacy_pattern_holds:privacy.held,privacy_source_exposed:false,errors,external_requests:external,
    model_requests:modelRequests,mobile_overflow:false,supabase_ingestion:'HOLD'};
}

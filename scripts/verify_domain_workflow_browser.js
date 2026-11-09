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
  if(await page.locator('#window-count').innerText()!=='8,511')throw Error('Existing vector denominator changed');
  const results=[];
  for(const code of ['01','02','03','04','05','06','07','08','09','10']){
    await page.getByRole('combobox',{name:'도메인',exact:true}).selectOption(code);
    const state=await page.evaluate(code=>{
      const data=JSON.parse(document.getElementById('report-data').textContent);
      const expected=data.summary.primary_domain_counts[code]||0;
      return {code,expected,actualText:document.getElementById('result-count').textContent,
        invalid:[...document.querySelectorAll('#rows .entry')].some(e=>!e.dataset.primary.startsWith(code+'.'))};
    },code);
    if(state.invalid||!state.actualText.startsWith(state.expected.toLocaleString('ko-KR')+'개'))throw Error('Domain filter mismatch '+code);
    results.push(state);
  }
  await page.getByRole('combobox',{name:'도메인',exact:true}).selectOption('02');
  await page.getByRole('combobox',{name:'업무',exact:true}).selectOption('02.07');
  await page.locator('#rows .entry').first().waitFor();
  if(await page.locator('#rows .entry').evaluateAll(rows=>rows.some(r=>r.dataset.primary!=='02.07')))throw Error('Workflow filter mismatch');
  await page.locator('#rows .entry summary').first().click();
  if(!await page.locator('#rows .entry .preview').first().innerText())throw Error('Actual public source preview missing');
  await page.getByLabel('해당 도메인·업무의 복수 직접 연결도 포함').check();
  const multiple=await page.locator('#result-count').innerText();
  await page.getByRole('combobox',{name:'도메인',exact:true}).selectOption('HOLD');
  const privacy=await page.evaluate(()=>{
    const data=JSON.parse(document.getElementById('report-data').textContent);
    const held=data.records.filter(r=>r.privacy_hold);
    return {held:held.length,exposed:held.some(r=>r.preview||r.links.length)};
  });
  if(privacy.held!==11||privacy.exposed)throw Error('Private source export boundary failed');
  await page.getByLabel('해당 도메인·업무의 복수 직접 연결도 포함').uncheck();
  await page.getByRole('combobox',{name:'도메인',exact:true}).selectOption('01');
  await page.screenshot({path:'output/playwright/domain-workflow-classification.png'});
  await page.setViewportSize({width:390,height:844});
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
  if(overflow||errors.length||external.length||modelRequests.length)throw Error('Browser or no-generation boundary failed');
  return {domain_filters:results,workflow_filter:true,multiple_direct_memberships:multiple,
    source_units:10205,existing_vector_windows:8511,privacy_pattern_holds:privacy.held,
    privacy_source_exposed:false,errors,external_requests:external,model_requests:modelRequests,
    mobile_overflow:false,supabase_ingestion:'HOLD'};
}

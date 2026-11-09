async page => {
  const errors=[],external=[],modelRequests=[],resourceErrors=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('response',r=>{if(r.status()>=400)resourceErrors.push(new URL(r.url()).pathname)});
  page.on('request',r=>{
    const u=new URL(r.url());
    if(['http:','https:'].includes(u.protocol)&&!['127.0.0.1','localhost'].includes(u.hostname))external.push(u.hostname);
    if(u.pathname.includes('/answer')||u.hostname.includes('openai.com'))modelRequests.push(u.pathname);
  });
  await page.setViewportSize({width:1280,height:1000});
  await page.goto('http://127.0.0.1:8853/');
  await page.locator('#rows .entry').first().waitFor();
  if(!(await page.locator('#result-count').innerText()).startsWith('917개'))throw Error('Complete table denominator missing');
  const filters=[];
  for(const value of ['DUPLICATE','ADDITIONAL','CONFLICT','HOLD']){
    await page.getByRole('combobox',{name:'판정',exact:true}).selectOption(value);
    const state=await page.evaluate(value=>{
      const d=JSON.parse(document.getElementById('data').textContent);
      return {value,expected:d.summary.asset_labels[value]||0,text:document.getElementById('result-count').textContent,
        invalid:[...document.querySelectorAll('#rows .entry')].some(r=>r.dataset.label!==value)};
    },value);
    if(state.invalid||!state.text.startsWith(state.expected.toLocaleString('ko-KR')+'개'))throw Error('Label filter mismatch');
    filters.push(state);
  }
  await page.getByRole('combobox',{name:'판정',exact:true}).selectOption('');
  for(const [stage,count] of [['priority_172',172],['remaining_745',745]]){
    await page.getByRole('combobox',{name:'처리 단계',exact:true}).selectOption(stage);
    if(!(await page.locator('#result-count').innerText()).startsWith(count+'개'))throw Error('Stage denominator mismatch');
  }
  await page.getByRole('combobox',{name:'처리 단계',exact:true}).selectOption('');
  await page.getByRole('searchbox').fill('K-117-A01-P0008-TG002');
  if(await page.locator('#rows .entry').count()!==1)throw Error('Table ID query mismatch');
  await page.locator('#rows .entry summary').click();
  await page.locator('#rows .entry img').waitFor({state:'visible'});
  await page.waitForFunction(()=>{const i=document.querySelector('#rows .entry img');return i&&i.complete&&i.naturalWidth>0});
  const imageOk=await page.locator('#rows .entry img').evaluate(img=>img.complete&&img.naturalWidth>0);
  if(!imageOk||!await page.locator('#rows .entry .source .quote').count())throw Error('Table/body source view missing');
  const frozen=await page.evaluate(()=>{
    const d=JSON.parse(document.getElementById('data').textContent);
    const held=d.records.filter(r=>r.privacy_hold);
    return {assets:d.records.length,occurrences:d.records.reduce((s,r)=>s+r.occurrences.length,0),
      privateExposed:held.some(r=>r.image_path||r.occurrences.some(o=>o.table_text||o.body_proofs.length))};
  });
  if(frozen.assets!==917||frozen.occurrences!==1014||frozen.privateExposed)throw Error('Source coverage or private boundary failed');
  await page.getByRole('searchbox').fill('');
  await page.evaluate(()=>window.scrollTo(0,0));
  await page.screenshot({path:'output/playwright/table-body-links.png'});
  await page.setViewportSize({width:390,height:844});
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
  if(overflow||errors.length||external.length||modelRequests.length||resourceErrors.length)throw Error('Browser or offline boundary failed');
  return {assets:917,source_occurrences:1014,label_filters:filters,stage_filters:true,
    table_and_body_proofs_visible:true,private_exposed:false,mobile_overflow:false,
    page_errors:errors,resource_errors:resourceErrors,external_requests:external,model_requests:modelRequests,supabase_ingestion:'HOLD'};
}

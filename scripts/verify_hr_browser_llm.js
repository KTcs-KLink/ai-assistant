// One actual generic HR question through browser -> BFF -> allowed corpus -> GPT -> citation UI.
async page => {
  await page.setViewportSize({width:1440,height:1000})
  await page.goto('http://127.0.0.1:8826/hr-check')
  await page.getByRole('button',{name:'가상 직원으로 기능 확인'}).click()
  await page.locator('#catalog article').first().waitFor()
  const question='육아휴직 기간은 어떤 조문에서 확인하나요?'
  await page.getByRole('textbox',{name:'일반 인사 업무 질문'}).fill(question)
  const pending=page.waitForResponse(r=>r.url().endsWith('/api/benefits/hr/answer')&&r.request().method()==='POST',{timeout:75000})
  await page.getByRole('button',{name:'근거와 함께 질문하기'}).click()
  const response=await pending
  const data=await response.json()
  if(response.status()!==200)throw Error('Live HR response status '+response.status()+' '+(response.headers()['x-klink-rag-failure']||''))
  await page.locator('#answer .status').first().waitFor()
  if(data.company!=='KEPCO'||data.ktcs_applicable||data.employee_data_sent||data.human_approved)throw Error('Research and employee boundary changed')
  await page.locator('#answer details summary').first().click()
  await page.locator('#answer-heading').scrollIntoViewIfNeeded()
  await page.screenshot({path:'output/playwright/hr-domain-live-answer.png',fullPage:false})
  return {question,http_status:response.status(),result:data,browser_rendered:true,citation_expanded:true,actual_model_calls:1}
}

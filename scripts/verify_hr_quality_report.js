// The report is self-contained and uses no model or database calls.
async page => {
  const errors=[]
  page.on('pageerror',e=>errors.push(e.message))
  await page.setViewportSize({width:1440,height:1000})
  await page.goto('http://127.0.0.1:8831/report.html')
  if(await page.locator('article.case').count()!==40)throw Error('Report must contain all forty cases')
  await page.locator('#split').selectOption('held_out_from_fix_selection')
  if(await page.locator('article.case').count()!==16)throw Error('Held-out filter count changed')
  await page.getByRole('button',{name:'원문 모두 펼치기'}).click()
  if(await page.locator('details.source[open]').count()!==16)throw Error('Original source expansion failed')
  await page.locator('#split').selectOption('')
  await page.locator('#search').fill('육아')
  if(!await page.locator('article.case').count())throw Error('Korean report search failed')
  await page.locator('#search').fill('')
  await page.screenshot({path:'output/playwright/hr-quality-report-desktop.png'})
  await page.setViewportSize({width:390,height:844})
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)
  await page.screenshot({path:'output/playwright/hr-quality-report-mobile.png'})
  if(overflow||errors.length)throw Error('Report layout or runtime failed')
  return {cases:40,held_out:16,source_expand:true,korean_search:true,mobile_overflow:false,errors}
}

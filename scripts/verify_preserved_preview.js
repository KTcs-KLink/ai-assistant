async function verifyPreservedPreview(page) {
  let api=0;const errors=[];
  page.on('request',r=>{if(new URL(r.url()).pathname.startsWith('/api/benefits'))api++});
  page.on('pageerror',e=>errors.push(e.message));
  await page.setViewportSize({width:1440,height:1040});
  await page.goto('http://127.0.0.1:8824/workspace');
  await page.getByRole('heading',{level:1}).waitFor();
  if(!(await page.getByRole('link',{name:/조건 충족 3/}).isVisible()))throw Error('Original preview changed');
  await page.locator('body').ariaSnapshot();
  await page.getByRole('navigation',{name:'직원 포털 메뉴'}).getByRole('link',{name:'AI 업무 도우미',exact:true}).click();
  await page.getByRole('heading',{level:1}).waitFor();
  await page.getByText('현재는 고정 예시 답변입니다.',{exact:false}).waitFor();
  if(api||errors.length)throw Error('Original demo connected to backend or had script errors');
  await page.getByRole('link',{name:'K:LINK 직원 포털 홈'}).click();
  return {status:'PASSED',previewUrl:'http://127.0.0.1:8824/workspace',apiRequests:api,pageErrors:errors,checks:['Original fictional recommendation counts','Original fixed-answer boundary','No backend request from preserved preview']};
}

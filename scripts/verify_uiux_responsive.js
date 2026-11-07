// Run with playwright-cli run-code --filename=scripts/verify_uiux_responsive.js
async (page) => {
  const checks = [], errors = [], dataRequests = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('request', r => { const u=new URL(r.url()); if(u.pathname.startsWith('/api/')||!['localhost','127.0.0.1'].includes(u.hostname)) dataRequests.push(u.origin+u.pathname); });
  const dimensions = [{width:360,height:800},{width:390,height:844},{width:768,height:1024},{width:1920,height:1080}];
  const routes = [{path:'', heading:'나에게 필요한 일, 오늘도 K:LINK와 함께.'},{path:'/benefits', heading:'나를 위한 혜택'},{path:'/assistant',heading:'궁금한 업무가 있나요?'},{path:'/library',heading:'규정과 양식, 한곳에서'},{path:'/preparations',heading:'차근차근, 신청 준비'},{path:'/profile',heading:'내 정보·동의 관리'},{path:'/login',heading:'오늘도 반가워요'}];
  for(const size of dimensions) {
    await page.setViewportSize(size);
    for(const route of routes) {
      await page.goto('http://127.0.0.1:8822/workspace'+route.path);
      await page.getByRole('heading',{name:route.heading,exact:true}).waitFor();
      const layout=await page.evaluate(()=>({viewport:innerWidth,doc:document.documentElement.scrollWidth,body:document.body.scrollWidth}));
      if(layout.doc>size.width+1||layout.body>size.width+1) throw new Error('Horizontal overflow '+JSON.stringify({size,route:route.path,...layout}));
      checks.push(`${size.width}px ${route.path||'/home'}: no page overflow`);
      if(size.width===390||size.width===768) await page.screenshot({path:`output/playwright/final-uiux-${route.path.slice(1)||'home'}-${size.width}.png`,fullPage:true});
    }
  }
  await page.setViewportSize({width:390,height:844});
  await page.goto('http://127.0.0.1:8822/workspace');
  await page.getByRole('button',{name:'전체 메뉴 열기'}).click();
  let dialog=page.getByRole('dialog');
  await dialog.getByRole('link',{name:'나의 혜택',exact:true}).click();
  if(await page.getByRole('dialog').count()) throw new Error('Mobile navigation did not close');
  checks.push('mobile menu navigates and closes');
  await page.getByRole('button',{name:'자녀 돌봄 지원금 자세히 보기'}).click();
  dialog=page.getByRole('dialog');
  await dialog.getByRole('tab',{name:'자격 조건'}).click();
  await page.screenshot({path:'output/playwright/final-uiux-benefit-drawer-390.png',fullPage:false});
  let bounds=await dialog.boundingBox();
  if(!bounds||bounds.x<0||bounds.x+bounds.width>391) throw new Error('Drawer outside mobile viewport');
  checks.push('mobile detail drawer fits viewport');
  await dialog.getByRole('button',{name:'AI에게 물어보기'}).click();
  const input=page.getByRole('textbox',{name:'AI에게 질문하기'});
  if(!(await input.inputValue()).includes('자녀 돌봄 지원금')) throw new Error('Benefit context missing in AI');
  checks.push('benefit to AI preserves selected context');
  await page.getByRole('button',{name:'질문 보내기'}).click();
  await page.locator('.kl-chat-message.assistant').waitFor();
  await page.locator('.kl-citation').click();
  await page.getByRole('heading',{name:'답변의 근거',exact:true}).waitFor();
  await page.screenshot({path:'output/playwright/final-uiux-assistant-source-390.png',fullPage:true});
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1);
  if(overflow) throw new Error('AI source creates mobile overflow');
  checks.push('mobile AI source panel fits');
  await page.getByRole('button',{name:'근거 패널 닫기'}).click();
  await page.getByRole('navigation',{name:'모바일 주요 메뉴'}).getByRole('link',{name:'자료',exact:true}).click();
  await page.getByRole('tab',{name:'신청 양식',exact:true}).click();
  await page.locator('.kl-document-row').filter({hasText:'출장신청·사전품의서'}).click();
  await page.getByRole('dialog').waitFor();
  await page.screenshot({path:'output/playwright/final-uiux-form-390.png',fullPage:true});
  await page.keyboard.press('Escape');
  checks.push('mobile library and form preparation works');
  if(errors.length) throw new Error('Runtime errors: '+JSON.stringify(errors));
  if(dataRequests.length) throw new Error('Unexpected external or API requests: '+JSON.stringify(dataRequests));
  checks.push('no runtime errors or API/third-party requests');
  return {count:checks.length,checks,errors,dataRequests};
}

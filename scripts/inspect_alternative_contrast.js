async function inspectAlternativeContrast(page) {
  await page.keyboard.press('Escape');
  const pages = [];
  for (const width of [1440, 390]) {
    await page.setViewportSize({width, height: width === 390 ? 844 : 1040});
    for (const path of ['', '/benefits', '/assistant', '/library', '/preparations', '/profile', '/login']) {
      await page.goto('http://127.0.0.1:8824/workspace' + path);
      await page.getByRole('heading', {level:1}).waitFor();
  const results = await page.evaluate(() => {
    const rgb = (text) => (text.match(/[\d.]+/g) || []).map(Number);
    const luminance = (color) => color.slice(0, 3).map((v) => v / 255).map((v) => v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4).reduce((sum, v, i) => sum + v * [.2126, .7152, .0722][i], 0);
    const groups = {};
    for (const el of document.querySelectorAll('.p-app *, .p-login *')) {
      const text = Array.from(el.childNodes).filter((node) => node.nodeType === 3).map((node) => node.textContent).join('').trim();
      if (!text || !el.checkVisibility() || el.closest('[disabled],.p-sr-only')) continue;
      let current = el, background = [255,255,255,1];
      while (current) { const value = rgb(getComputedStyle(current).backgroundColor); if (value.length >= 3 && (value.length < 4 || value[3] >= .99)) { background = value; break; } current = current.parentElement; }
      const style = getComputedStyle(el), color = rgb(style.color);
      const a = luminance(color), b = luminance(background), ratio = (Math.max(a,b) + .05) / (Math.min(a,b) + .05);
      const large = parseFloat(style.fontSize) >= 24 || parseFloat(style.fontSize) >= 18.66 && parseFloat(style.fontWeight) >= 700;
      if (ratio < (large ? 3 : 4.5)) { const key = style.color + ' on ' + background.slice(0,3).join(','); if (!groups[key]) groups[key] = { ratio: +ratio.toFixed(2), samples: [] }; if (groups[key].samples.length < 2) groups[key].samples.push({ text: text.slice(0,65), selector: el.className, size: style.fontSize }); }
    }
    return { width: innerWidth, documentWidth: document.documentElement.scrollWidth, lowContrast: groups };
  });
      pages.push({path:'/workspace' + path, ...results});
      if (path === '/login') await page.screenshot({path:'output/playwright/' + (width === 390 ? 'mobile' : 'desktop') + '-login.png'});
    }
  }
  await page.setViewportSize({width:1440,height:1040});
  await page.goto('http://127.0.0.1:8824/workspace');
  return {status:pages.every((item) => Object.keys(item.lowContrast).length === 0) ? 'PASSED' : 'NEEDS_REVIEW', scope:'Simple computed foreground/background text contrast check; not a full accessibility audit', pages};
}

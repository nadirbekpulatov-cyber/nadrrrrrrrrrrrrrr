// Снимает исходники для видео: старый и новый дашборд, тёмную тему и телефон
const { chromium } = require('playwright');
const path = require('path');
const root = path.resolve(__dirname, '..', '..');
const out = (f) => path.resolve(__dirname, '..', 'assets', f);
(async () => {
  const b = await chromium.launch();
  async function shot(file, url, opts, act) {
    const ctx = await b.newContext({ viewport: opts.vp, deviceScaleFactor: opts.dsf || 2, colorScheme: opts.scheme || 'light' });
    const p = await ctx.newPage();
    await p.goto('file://' + url, { waitUntil: 'load', timeout: 30000 }).catch(() => {});
    await p.evaluate(() => document.fonts && document.fonts.ready);
    await p.waitForTimeout(opts.wait || 600);
    if (act) await act(p);
    await p.screenshot({ path: out(file), fullPage: !!opts.full });
    await ctx.close();
    console.log('ok', file);
  }
  const dash = root + '/nadir-dashboard.html';
  await shot('new-light.png', dash, { vp: { width: 1440, height: 900 }, full: true });
  await shot('new-dark.png', dash, { vp: { width: 1440, height: 900 }, full: true, scheme: 'dark' });
  await shot('new-mobile.png', dash, { vp: { width: 390, height: 844 }, dsf: 3, full: true, scheme: 'dark' });
  await shot('old.png', __dirname + '/old-dashboard.html', { vp: { width: 1440, height: 900 }, wait: 4000 });
  await b.close();
})();

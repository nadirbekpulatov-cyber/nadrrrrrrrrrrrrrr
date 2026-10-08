// Рендер композиции в MP4 кадр за кадром: node render.js [--fps 30] [--from 0] [--to DURATION] [--out out.mp4]
// Режим проверки: node render.js --stills 5,20,35 --out sheet-dir
const { chromium } = require('playwright');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const arg = (k, d) => { const i = process.argv.indexOf('--' + k); return i > -1 ? process.argv[i + 1] : d; };
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  p.on('pageerror', (e) => console.error('pageerror:', e.message));
  await p.goto('file://' + path.resolve(__dirname, 'composition.html'), { waitUntil: 'load' });
  await p.evaluate(() => window.ready);
  await p.waitForTimeout(300);
  const stage = await p.$('#stage');
  const stills = arg('stills');
  if (stills) {
    const dir = path.resolve(arg('out', 'stills'));
    fs.mkdirSync(dir, { recursive: true });
    for (const t of stills.split(',').map(Number)) {
      await p.evaluate((t) => window.seek(t), t);
      await stage.screenshot({ path: path.join(dir, `t${String(t).padStart(6, '0')}.png`) });
    }
    await b.close();
    return;
  }
  const fps = +arg('fps', 30), from = +arg('from', 0);
  const to = +arg('to', await p.evaluate(() => window.DURATION));
  const out = path.resolve(arg('out', 'out.mp4'));
  const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(fps), '-c:v', 'mjpeg', '-i', '-',
    '-c:v', 'libx264', '-preset', 'medium', '-crf', '17', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out], { stdio: ['pipe', 'inherit', 'inherit'] });
  const n = Math.round((to - from) * fps);
  const t0 = Date.now();
  for (let i = 0; i < n; i++) {
    await p.evaluate((t) => window.seek(t), from + i / fps);
    const buf = await stage.screenshot({ type: 'jpeg', quality: 94 });
    if (!ff.stdin.write(buf)) await new Promise((r) => ff.stdin.once('drain', r));
    if (i % (fps * 10) === 0) console.log(`frame ${i}/${n}  ${((Date.now() - t0) / 1000).toFixed(0)}s`);
  }
  ff.stdin.end();
  await new Promise((r) => ff.on('close', r));
  console.log('done', out, ((Date.now() - t0) / 1000).toFixed(0) + 's');
  await b.close();
})();

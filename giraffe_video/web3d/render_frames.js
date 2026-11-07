// usage: node render_frames.js items.json outdir   (items: [{key,scene,t,T}])
const { chromium } = require('playwright'); const http = require('http'), fs = require('fs'), path = require('path');
const root = path.resolve(__dirname, '..');
const items = JSON.parse(fs.readFileSync(process.argv[2])), out = process.argv[3]; fs.mkdirSync(out, { recursive: true });
const types = { '.js': 'text/javascript', '.html': 'text/html', '.json': 'application/json', '.jpg': 'image/jpeg' };
const srv = http.createServer((q, r) => { const p = path.join(root, decodeURIComponent(q.url.split('?')[0]));
  fs.readFile(p, (e, d) => { if (e) { r.writeHead(404); r.end(); } else { r.writeHead(200, { 'content-type': types[path.extname(p)] || 'application/octet-stream' }); r.end(d); } }); });
(async () => {
  await new Promise(r => srv.listen(0, r)); const port = srv.address().port;
  const br = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--no-sandbox'] });
  const pg = await br.newPage({ viewport: { width: 720, height: 1280 } });
  pg.on('pageerror', e => console.error('PAGEERR', e.message)); pg.on('console', m => { if (m.type() === 'error') console.error('CONSOLE', m.text()); });
  await pg.goto(`http://127.0.0.1:${port}/web3d/scene.html`); await pg.evaluate(() => window.__ready);
  const meta = {}; let n = 0, t0 = Date.now();
  for (const it of items) {
    const f = path.join(out, it.key + '.jpg'); const mf = path.join(out, it.key + '.json');
    if (fs.existsSync(f) && fs.existsSync(mf)) continue;
    const r = await pg.evaluate(([s, t, T]) => { const o = window.renderFrame(s, t, T); return [o, window.grab()]; }, [it.scene, it.t, it.T]);
    fs.writeFileSync(f, Buffer.from(r[1].split(',')[1], 'base64')); fs.writeFileSync(mf, JSON.stringify(r[0]));
    if (++n % 20 === 0) console.log(n, '/', items.length, ((Date.now() - t0) / n / 1000).toFixed(2), 's/frame');
  }
  await br.close(); srv.close(); console.log('done', n);
})();

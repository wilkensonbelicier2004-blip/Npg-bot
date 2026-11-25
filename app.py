import os
from flask import Flask, jsonify, Response

app = Flask(__name__)

PAJ = r"""<!doctype html><html lang="ht"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#0b0f14">
<meta name="google" content="notranslate">
<link rel="manifest" href="/manifest.json">
<link rel="icon" href="/icon.svg"><link rel="apple-touch-icon" href="/icon.svg">
<meta name="apple-mobile-web-app-capable" content="yes">
<title>NPG Pocket Bot</title>
<style>
body{margin:0;padding:12px;background:#0b0f14;color:#e5e7eb;font-family:sans-serif}
h1{font-size:20px;margin:4px 0}
#st{font-size:12px;color:#9ca3af;margin-bottom:8px}
button{background:#1f2937;color:#fff;border:0;border-radius:8px;padding:8px 12px;margin:0 6px 10px 0}
.kat{background:#111827;border-radius:10px;padding:10px;margin-bottom:8px}
.ev{background:#111827;border-radius:10px;padding:10px;margin-bottom:8px;font-size:14px;border-left:5px solid #6b7280}
.ev.achte{border-color:#22c55e}.ev.vann{border-color:#ef4444}.ev.soti{border-color:#f59e0b}
.achte{color:#22c55e;font-weight:bold}.vann{color:#ef4444;font-weight:bold}.atann{color:#9ca3af}
.pti{font-size:11px;color:#6b7280}.er{font-size:12px;color:#f87171}
h2{font-size:16px;margin:14px 0 6px}
</style></head><body>
<h1>NPG POCKET BOT</h1>
<div id="st">Ap kòmanse...</div>
<button onclick="nt()">Aktive notifikasyon</button>
<button onclick="rezet()">Efase istwa</button>
<h2>Mache a</h2><div id="mc"></div>
<h2>Siyal yo</h2><div id="ev"></div>
<script>
const PEZ = {
  BTCUSDT: {k: 'XBTUSDT', c: 'BTC-USD'},
  ETHUSDT: {k: 'ETHUSDT', c: 'ETH-USD'},
  BNBUSDT: {},
  SOLUSDT: {k: 'SOLUSDT', c: 'SOL-USD'},
  XRPUSDT: {k: 'XRPUSDT', c: 'XRP-USD'}
};
const SL = 0.005, TP = 0.01, PAUS = 20000, MAX_AJE = 120000;
let eta = {pozisyon: {}, istwa: [], stat: {gen: 0, pet: 0}, dernye: {}, kont: 0};
try {
  const s = localStorage.getItem('npg_eta');
  if (s) eta = Object.assign(eta, JSON.parse(s));
} catch (e) {}
function sove() { try { localStorage.setItem('npg_eta', JSON.stringify(eta)); } catch (e) {} }
function rezet() {
  eta = {pozisyon: {}, istwa: [], stat: {gen: 0, pet: 0}, dernye: {}, kont: 0};
  sove(); rann();
}
const mache = {};
const premye = {};
let tou = 0, etap = 'ap kòmanse', update = '';

const esc = s => String(s).replace(/[&<>]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;'}[c]));
function nt() { if ('Notification' in window) Notification.requestPermission(); }

async function lis(url) {
  const c = new AbortController();
  const t = setTimeout(() => c.abort(), 6000);
  try {
    const r = await fetch(url, {signal: c.signal});
    if (!r.ok) throw new Error('HTTP ' + r.status);
    return await r.json();
  } finally { clearTimeout(t); }
}

function binance(host) {
  return async s => {
    const d = await lis(host + '/api/v3/klines?symbol=' + s + '&interval=1m&limit=100');
    return [d.map(k => k[0]), d.map(k => parseFloat(k[4]))];
  };
}
const SOUS = [
  ['Binance', binance('https://api.binance.com')],
  ['Binance Vision', binance('https://data-api.binance.vision')],
  ['Kraken', async s => {
    const m = PEZ[s].k;
    if (!m) throw new Error('pa disponib');
    const d = await lis('https://api.kraken.com/0/public/OHLC?pair=' + m + '&interval=1');
    if (d.error && d.error.length) throw new Error(d.error[0]);
    const key = Object.keys(d.result).filter(x => x !== 'last')[0];
    const rows = d.result[key].slice(-100);
    return [rows.map(r => r[0] * 1000), rows.map(r => parseFloat(r[4]))];
  }],
  ['Coinbase', async s => {
    const m = PEZ[s].c;
    if (!m) throw new Error('pa disponib');
    const d = await lis('https://api.exchange.coinbase.com/products/' + m + '/candles?granularity=60');
    const rows = d.slice(0, 100).reverse();
    return [rows.map(r => r[0] * 1000), rows.map(r => parseFloat(r[4]))];
  }]
];

async function jwennDone(s) {
  const er = [];
  for (const [non, fn] of SOUS) {
    try {
      const [tan, prix] = await fn(s);
      if (prix.length < 30) throw new Error('pa ase done');
      return {non, tan, prix};
    } catch (e) {
      er.push(non + ': ' + String(e.message || e).slice(0, 40));
    }
  }
  throw new Error(er.join(' | '));
}

function ema(prix, n) {
  const k = 2 / (n + 1);
  let e = prix[0];
  const rez = [e];
  for (let i = 1; i < prix.length; i++) {
    e = prix[i] * k + e * (1 - k);
    rez.push(e);
  }
  return rez;
}
function rsi(prix, n) {
  n = n || 14;
  const gain = [], pert = [];
  for (let i = 1; i < prix.length; i++) {
    const d = prix[i] - prix[i - 1];
    gain.push(Math.max(d, 0));
    pert.push(Math.max(-d, 0));
  }
  let g = gain.slice(0, n).reduce((a, b) => a + b, 0) / n;
  let p = pert.slice(0, n).reduce((a, b) => a + b, 0) / n;
  for (let i = n; i < gain.length; i++) {
    g = (g * (n - 1) + gain[i]) / n;
    p = (p * (n - 1) + pert[i]) / n;
  }
  if (p === 0) return 100;
  return 100 - 100 / (1 + g / p);
}
function kalkile(prix) {
  const e9 = ema(prix, 9), e21 = ema(prix, 21);
  const r = rsi(prix.slice(0, -1));
  const L = e9.length;
  let siyal = 'ATANN';
  if (e9[L - 3] < e21[L - 3] && e9[L - 2] > e21[L - 2] && r < 70) siyal = 'ACHTE';
  else if (e9[L - 3] > e21[L - 3] && e9[L - 2] < e21[L - 2] && r > 30) siyal = 'VANN';
  return [siyal, e9[L - 1], e21[L - 1], r];
}

function pl(p, pri) {
  if (p.sans === 'ACHTE') return (pri - p.antre) / p.antre * 100;
  return (p.antre - pri) / p.antre * 100;
}
function notifye(x) {
  try { if (navigator.vibrate) navigator.vibrate(400); } catch (e) {}
  try {
    if ('Notification' in window && Notification.permission === 'granted') {
      const tit = x.sym + ' ' + x.tip + ' ' + x.sans;
      if (navigator.serviceWorker) {
        navigator.serviceWorker.ready.then(reg => reg.showNotification(tit, {body: x.liy[0]}));
      } else { new Notification(tit, {body: x.liy[0]}); }
    }
  } catch (e) {}
}
function evenman(tip, sym, sans, liy, le) {
  eta.kont++;
  const x = {id: eta.kont, tip: tip, sym: sym, sans: sans, le: le, liy: liy};
  eta.istwa.unshift(x);
  eta.istwa.length = Math.min(eta.istwa.length, 50);
  notifye(x);
}
function femen(sym, pri, rezon, le) {
  const p = eta.pozisyon[sym];
  delete eta.pozisyon[sym];
  const v = pl(p, pri);
  let rez;
  if (v > 0) { eta.stat.gen++; rez = 'GEN'; } else { eta.stat.pet++; rez = 'PET'; }
  evenman('SOTI', sym, p.sans, [
    'Rezon: ' + rezon,
    'Antre: ' + p.antre.toFixed(4) + ' | Soti: ' + pri.toFixed(4),
    'Rezilta: ' + rez + ' ' + v.toFixed(2) + '%',
    'MT5: fèmen trade a kounye a'], le);
}
function louvri(sym, siyal, pri, r, le) {
  let sl, tp;
  if (siyal === 'ACHTE') { sl = pri * (1 - SL); tp = pri * (1 + TP); }
  else { sl = pri * (1 + SL); tp = pri * (1 - TP); }
  eta.pozisyon[sym] = {sans: siyal, antre: pri, sl: sl, tp: tp};
  evenman('ANTRE', sym, siyal, [
    siyal + ' @ ' + pri.toFixed(4) + ' | RSI ' + Math.round(r),
    'MT5 -> SL: ' + sl.toFixed(4) + ' | TP: ' + tp.toFixed(4),
    'Pocket Option -> ekspirasyon: 1 a 3 min'], le);
}
function trete(sym, sous, res, pri, tan, le) {
  const siyal = res[0], a = res[1], b = res[2], r = res[3];
  const p0 = eta.pozisyon[sym];
  if (p0) {
    if (p0.sans === 'ACHTE') {
      if (pri <= p0.sl) femen(sym, pri, 'SL touche', le);
      else if (pri >= p0.tp) femen(sym, pri, 'TP touche', le);
    } else {
      if (pri >= p0.sl) femen(sym, pri, 'SL touche', le);
      else if (pri <= p0.tp) femen(sym, pri, 'TP touche', le);
    }
  }
  const dk = tan[tan.length - 2];
  if (!premye[sym]) {
    premye[sym] = true;
    if (siyal !== 'ATANN') eta.dernye[sym] = dk;
  } else if (siyal !== 'ATANN' && eta.dernye[sym] !== dk) {
    eta.dernye[sym] = dk;
    if (Date.now() - (dk + 60000) <= MAX_AJE) {
      const p = eta.pozisyon[sym];
      if (p && p.sans !== siyal) femen(sym, pri, 'Kwazman kontrè', le);
      if (!eta.pozisyon[sym]) louvri(sym, siyal, pri, r, le);
    }
  }
  const p = eta.pozisyon[sym];
  mache[sym] = {
    pri: pri, tandans: a > b ? 'monte' : 'desann', rsi: Math.round(r),
    trade: p ? {sans: p.sans, pl: +pl(p, pri).toFixed(2)} : null, sous: sous
  };
}

function rann() {
  document.getElementById('st').textContent =
    'Mizajou: ' + update + ' | Tou #' + tou + ' | ' + etap + ' | GEN ' + eta.stat.gen + ' / PET ' + eta.stat.pet;
  let h = '';
  for (const sym of Object.keys(mache)) {
    const m = mache[sym];
    if (m.err) {
      h += '<div class="kat"><b>' + esc(sym) + '</b><br><span class="er">' + esc(m.err) + '</span></div>';
      continue;
    }
    let b = '<span class="atann">ATANN</span>';
    if (m.trade) {
      b = '<span class="' + (m.trade.sans === 'ACHTE' ? 'achte' : 'vann') + '">TRADE ' + m.trade.sans + ' | P/L ' + m.trade.pl + '%</span>';
    }
    h += '<div class="kat"><b>' + esc(sym) + '</b> ' + m.pri.toFixed(m.pri < 10 ? 4 : 2) +
      '<br>Mache a ap ' + m.tandans + ' | RSI ' + m.rsi + '<br>' + b +
      '<br><span class="pti">Sous: ' + esc(m.sous) + '</span></div>';
  }
  document.getElementById('mc').innerHTML = h || '<p class="atann">Ap tann premye done yo...</p>';
  let e = '';
  for (const x of eta.istwa) {
    const k = x.tip === 'ANTRE' ? (x.sans === 'ACHTE' ? 'achte' : 'vann') : 'soti';
    e += '<div class="ev ' + k + '"><b>' + x.le + ' ' + esc(x.sym) + ' - ' + x.tip + '</b><br>' + x.liy.map(esc).join('<br>') + '</div>';
  }
  document.getElementById('ev').innerHTML = e || '<p class="atann">Pa gen siyal ankò.</p>';
}

async function tour() {
  const le = new Date().toLocaleTimeString('fr-FR');
  for (const sym of Object.keys(PEZ)) {
    etap = 'ap li ' + sym; rann();
    try {
      const d = await jwennDone(sym);
      trete(sym, d.non, kalkile(d.prix), d.prix[d.prix.length - 1], d.tan, le);
    } catch (e) {
      mache[sym] = {err: String(e.message || e).slice(0, 300)};
    }
    rann();
  }
  tou++; update = le; etap = 'ap tann pwochen tou';
  sove(); rann();
}
async function bouk() {
  while (true) {
    try { await tour(); } catch (e) { etap = 'erè: ' + e; rann(); }
    await new Promise(r => setTimeout(r, PAUS));
  }
}

async function kenbe() {
  try { if ('wakeLock' in navigator) await navigator.wakeLock.request('screen'); } catch (e) {}
}
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible') kenbe();
});
kenbe();
rann();
bouk();
if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js');
</script></body></html>"""

ICON = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
        '<rect width="100" height="100" rx="20" fill="#0b0f14"/>'
        '<path d="M15 70 L40 45 L55 60 L85 25" stroke="#22c55e" stroke-width="8" '
        'fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>')

@app.route("/")
def lakay():
    return Response(PAJ, mimetype="text/html")

@app.route("/sante")
def sante():
    return "ok"

@app.route("/manifest.json")
def manifest():
    return jsonify({"name": "NPG Pocket Bot", "short_name": "NPG Bot",
                    "start_url": "/", "display": "standalone",
                    "background_color": "#0b0f14", "theme_color": "#0b0f14",
                    "icons": [{"src": "/icon.svg", "sizes": "any",
                               "type": "image/svg+xml"}]})

@app.route("/icon.svg")
def icon():
    return Response(ICON, mimetype="image/svg+xml")

@app.route("/sw.js")
def sw():
    return Response("self.addEventListener('fetch', function(e){});",
                    mimetype="application/javascript")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

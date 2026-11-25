import json
import os
import socket
import time
import threading
from urllib.request import urlopen, Request
from datetime import datetime, timezone, timedelta
from flask import Flask, jsonify, Response

socket.setdefaulttimeout(6)

NTFY_TOPIC = "npg-bot-58214-sam"
PAUS = 20
MAX_AJE = 120
SL_C, TP_C = 0.005, 0.01
SL_F, TP_F = 0.001, 0.002
FICHYE = "state.json"

PEZ = {
    "BTCUSDT": {"n": "BTC/USDT", "b": "BTCUSDT", "k": "XBTUSDT", "c": "BTC-USD"},
    "ETHUSDT": {"n": "ETH/USDT", "b": "ETHUSDT", "k": "ETHUSDT", "c": "ETH-USD"},
    "BNBUSDT": {"n": "BNB/USDT", "b": "BNBUSDT"},
    "SOLUSDT": {"n": "SOL/USDT", "b": "SOLUSDT", "k": "SOLUSDT", "c": "SOL-USD"},
    "XRPUSDT": {"n": "XRP/USDT", "b": "XRPUSDT", "k": "XRPUSDT", "c": "XRP-USD"},
    "EURUSD": {"n": "EUR/USD", "f": True, "b": "EURUSDT", "k": "EURUSD"},
    "GBPUSD": {"n": "GBP/USD", "f": True, "b": "GBPUSDT", "k": "GBPUSD"},
    "AUDUSD": {"n": "AUD/USD", "f": True, "b": "AUDUSDT", "k": "AUDUSD"},
    "USDJPY": {"n": "USD/JPY", "f": True, "k": "USDJPY"},
    "USDCAD": {"n": "USD/CAD", "f": True, "k": "USDCAD"},
    "USDCHF": {"n": "USD/CHF", "f": True, "k": "USDCHF"},
}

try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("America/Port-au-Prince")
except Exception:
    TZ = timezone(timedelta(hours=-5))

def kounye():
    return datetime.now(TZ).strftime("%H:%M:%S")

app = Flask(__name__)
lock = threading.Lock()
premye = set()
fil = {"mache": False}
eta = {"mache": {}, "pozisyon": {}, "istwa": [], "stat": {"gen": 0, "pet": 0},
       "dernye": {}, "update": "", "kont": 0, "etap": "ap kòmanse", "tou": 0,
       "ntfy": "poko voye anyen"}

if os.path.exists(FICHYE):
    try:
        with open(FICHYE, encoding="utf-8") as f:
            eta.update(json.load(f))
    except Exception:
        pass

def sove():
    try:
        with open(FICHYE, "w", encoding="utf-8") as f:
            json.dump(eta, f)
    except Exception:
        pass

def nom(s):
    return PEZ.get(s, {}).get("n", s)

def fmt(p):
    if p < 10:
        return "%.5f" % p
    if p < 1000:
        return "%.3f" % p
    return "%.2f" % p

def voye(titl, mesaj, tag):
    try:
        req = Request("https://ntfy.sh/" + NTFY_TOPIC, data=mesaj.encode("utf-8"),
                      headers={"Title": titl, "Priority": "high", "Tags": tag})
        urlopen(req, timeout=8).read()
        eta["ntfy"] = "dènye alèt voye " + kounye()
        return "ok"
    except Exception as e:
        eta["ntfy"] = "erè alèt: " + str(e)[:60]
        return "erè: " + str(e)[:80]

def lis(url):
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return json.loads(urlopen(req, timeout=6).read())

def fetch_binance(host):
    def f(sym):
        m = PEZ[sym].get("b")
        if not m:
            raise Exception("pa disponib")
        d = lis(host + "/api/v3/klines?symbol=" + m + "&interval=1m&limit=100")
        return [k[0] for k in d], [float(k[4]) for k in d]
    return f

def fetch_kraken(sym):
    m = PEZ[sym].get("k")
    if not m:
        raise Exception("pa disponib")
    d = lis("https://api.kraken.com/0/public/OHLC?pair=" + m + "&interval=1")
    if d.get("error"):
        raise Exception(str(d["error"])[:60])
    rez = d["result"]
    kle = [k for k in rez if k != "last"][0]
    rows = rez[kle][-100:]
    return [int(r[0]) * 1000 for r in rows], [float(r[4]) for r in rows]

def fetch_coinbase(sym):
    m = PEZ[sym].get("c")
    if not m:
        raise Exception("pa disponib")
    d = lis("https://api.exchange.coinbase.com/products/" + m + "/candles?granularity=60")
    rows = d[:100][::-1]
    return [int(r[0]) * 1000 for r in rows], [float(r[4]) for r in rows]

SOUS = [
    ("Binance Vision", fetch_binance("https://data-api.binance.vision")),
    ("Kraken", fetch_kraken),
    ("Coinbase", fetch_coinbase),
    ("Binance.US", fetch_binance("https://api.binance.us")),
    ("Binance", fetch_binance("https://api.binance.com")),
]

def jwenn_done(sym):
    erè = []
    for non, fn in SOUS:
        try:
            tan, prix = fn(sym)
            if len(prix) < 30:
                raise Exception("pa ase done")
            return non, tan, prix
        except Exception as e:
            erè.append(non + ": " + str(e)[:40])
    raise Exception(" | ".join(erè))

def ema(prix, n):
    k = 2 / (n + 1)
    e = prix[0]
    rez = [e]
    for p in prix[1:]:
        e = p * k + e * (1 - k)
        rez.append(e)
    return rez

def rsi(prix, n=14):
    gain, pert = [], []
    for i in range(1, len(prix)):
        d = prix[i] - prix[i - 1]
        gain.append(max(d, 0))
        pert.append(max(-d, 0))
    g = sum(gain[:n]) / n
    p = sum(pert[:n]) / n
    for i in range(n, len(gain)):
        g = (g * (n - 1) + gain[i]) / n
        p = (p * (n - 1) + pert[i]) / n
    if p == 0:
        return 100
    return 100 - 100 / (1 + g / p)

def kalkile(prix):
    e9 = ema(prix, 9)
    e21 = ema(prix, 21)
    r = rsi(prix[:-1])
    siyal = "ATANN"
    if e9[-3] < e21[-3] and e9[-2] > e21[-2] and r < 70:
        siyal = "ACHTE"
    elif e9[-3] > e21[-3] and e9[-2] < e21[-2] and r > 30:
        siyal = "VANN"
    return siyal, e9[-1], e21[-1], r

def pl_pct(p, pri):
    if p["sans"] == "ACHTE":
        return (pri - p["antre"]) / p["antre"] * 100
    return (p["antre"] - pri) / p["antre"] * 100

def evenman(tip, sym, sans, liy, le):
    eta["kont"] += 1
    eta["istwa"].insert(0, {"id": eta["kont"], "tip": tip, "sym": nom(sym),
                            "sans": sans, "le": le, "liy": liy})
    del eta["istwa"][50:]
    tag = "green_circle" if (tip == "ANTRE" and sans == "ACHTE") else (
        "red_circle" if tip == "ANTRE" else "checkered_flag")
    titl = "NPG " + nom(sym) + " " + tip + " " + sans
    threading.Thread(target=voye, args=(titl, "\n".join(liy), tag), daemon=True).start()

def femen(sym, pri, rezon, le):
    p = eta["pozisyon"].pop(sym)
    pl = pl_pct(p, pri)
    if pl > 0:
        eta["stat"]["gen"] += 1
        rez = "GEN"
    else:
        eta["stat"]["pet"] += 1
        rez = "PET"
    evenman("SOTI", sym, p["sans"], [
        "Rezon: " + rezon,
        "Antre: " + fmt(p["antre"]) + " | Soti: " + fmt(pri),
        "Rezilta: " + rez + " " + str(round(pl, 2)) + "%",
        "Fèmen trade a kounye a"], le)

def louvri(sym, siyal, pri, r, le):
    fx = PEZ[sym].get("f")
    SL = SL_F if fx else SL_C
    TP = TP_F if fx else TP_C
    if siyal == "ACHTE":
        sl, tp = pri * (1 - SL), pri * (1 + TP)
    else:
        sl, tp = pri * (1 + SL), pri * (1 - TP)
    eta["pozisyon"][sym] = {"sans": siyal, "antre": pri, "sl": sl, "tp": tp}
    evenman("ANTRE", sym, siyal, [
        siyal + " @ " + fmt(pri) + " | RSI " + str(round(r)),
        "MT5 -> SL: " + fmt(sl) + " | TP: " + fmt(tp),
        "Pocket Option -> ekspirasyon: 1 a 3 min"], le)

def trete(sym, sous, siyal, a, b, r, pri, tan, le):
    p0 = eta["pozisyon"].get(sym)
    if p0:
        if p0["sans"] == "ACHTE":
            if pri <= p0["sl"]:
                femen(sym, pri, "SL touche", le)
            elif pri >= p0["tp"]:
                femen(sym, pri, "TP touche", le)
        else:
            if pri >= p0["sl"]:
                femen(sym, pri, "SL touche", le)
            elif pri <= p0["tp"]:
                femen(sym, pri, "TP touche", le)
    dk = tan[-2]
    if sym not in premye:
        premye.add(sym)
        if siyal != "ATANN":
            eta["dernye"][sym] = dk
    elif siyal != "ATANN" and eta["dernye"].get(sym) != dk:
        eta["dernye"][sym] = dk
        fre = (time.time() * 1000 - (dk + 60000)) <= MAX_AJE * 1000
        if fre:
            p = eta["pozisyon"].get(sym)
            if p and p["sans"] != siyal:
                femen(sym, pri, "Kwazman kontrè", le)
            if sym not in eta["pozisyon"]:
                louvri(sym, siyal, pri, r, le)
    p = eta["pozisyon"].get(sym)
    trade = None
    if p:
        trade = {"sans": p["sans"], "pl": round(pl_pct(p, pri), 2)}
    eta["mache"][sym] = {"pri": pri, "tandans": "monte" if a > b else "desann",
                         "rsi": round(r), "trade": trade, "sous": sous}

def boukle():
    while True:
        try:
            le = kounye()
            for sym in PEZ:
                eta["etap"] = "ap li " + nom(sym)
                try:
                    sous, tan, prix = jwenn_done(sym)
                    siyal, a, b, r = kalkile(prix)
                    with lock:
                        trete(sym, sous, siyal, a, b, r, prix[-1], tan, le)
                except Exception as e:
                    with lock:
                        eta["mache"][sym] = {"err": str(e)[:300]}
            with lock:
                eta["tou"] += 1
                eta["update"] = le
                eta["etap"] = "ap tann pwochen tou"
                sove()
        except Exception as e:
            eta["etap"] = "erè bòkl: " + str(e)[:100]
        time.sleep(PAUS)

def demare():
    if not fil["mache"]:
        fil["mache"] = True
        threading.Thread(target=boukle, daemon=True).start()

@app.before_request
def avan():
    demare()

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
<h1>NPG POCKET BOT</h1><div id="st">Ap chaje...</div>
<button onclick="tes()">Voye alèt tès</button>
<h2>Siyal yo</h2><div id="ev"></div>
<h2>Mache a</h2><div id="mc"></div>
<script>
const esc = s => String(s).replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
function fmt(p){ return p < 10 ? p.toFixed(5) : (p < 1000 ? p.toFixed(3) : p.toFixed(2)); }
async function tes(){
  try { const r = await fetch('/test'); alert('Rezilta: ' + await r.text()); }
  catch(e){ alert('Erè rezo'); }
}
async function chaje(){
  const st = document.getElementById('st');
  try{
    const d = await (await fetch('/api/state')).json();
    st.textContent = 'Mizajou: ' + d.update + ' | Tou #' + d.tou + ' | ' + d.etap +
      ' | GEN ' + d.stat.gen + ' / PET ' + d.stat.pet + ' | ' + d.ntfy;
    let h = '';
    for (const [sym, m] of Object.entries(d.mache)){
      if (m.err){ h += `<div class="kat"><b>${esc(sym)}</b><br><span class="er">${esc(m.err)}</span></div>`; continue; }
      let b = '<span class="atann">ATANN</span>';
      if (m.trade){
        b = `<span class="${m.trade.sans=='ACHTE'?'achte':'vann'}">TRADE ${m.trade.sans} | P/L ${m.trade.pl}%</span>`;
      }
      h += `<div class="kat"><b>${esc(sym)}</b> ${fmt(m.pri)}<br>Mache a ap ${m.tandans} | RSI ${m.rsi}<br>${b}<br><span class="pti">Sous: ${esc(m.sous)}</span></div>`;
    }
    document.getElementById('mc').innerHTML = h || '<p class="atann">Ap tann premye done yo...</p>';
    let e = '';
    for (const x of d.istwa){
      const k = x.tip=='ANTRE' ? (x.sans=='ACHTE'?'achte':'vann') : 'soti';
      e += `<div class="ev ${k}"><b>${x.le} ${esc(x.sym)} - ${x.tip}</b><br>${x.liy.map(esc).join('<br>')}</div>`;
    }
    document.getElementById('ev').innerHTML = e || '<p class="atann">Pa gen siyal ankò.</p>';
  }catch(err){ st.textContent = 'Pa gen koneksyon...'; }
}
chaje(); setInterval(chaje, 10000);
if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js');
</script></body></html>"""

ICON = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
        '<rect width="100" height="100" rx="20" fill="#0b0f14"/>'
        '<path d="M15 70 L40 45 L55 60 L85 25" stroke="#22c55e" stroke-width="8" '
        'fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>')

@app.route("/")
def lakay():
    return Response(PAJ, mimetype="text/html")

@app.route("/api/state")
def api():
    with lock:
        return jsonify(eta)

@app.route("/sante")
def sante():
    return "ok"

@app.route("/test")
def test():
    return voye("NPG test", "Si w wè mesaj sa a, alèt yo mache.", "white_check_mark")

@app.route("/diag")
def diag():
    rez = {}
    for non, fn in SOUS:
        try:
            tan, prix = fn("BTCUSDT")
            rez[non] = "OK " + str(len(prix)) + " bougi, dènye pri " + str(prix[-1])
        except Exception as e:
            rez[non] = "ERÈ: " + str(e)[:100]
    return jsonify(rez)

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

demare()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

import json
import os
import time
import threading
from urllib.request import urlopen
from datetime import datetime
from flask import Flask, jsonify, Response

PEZ = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT"]
PAUS = 20
SL_PCT = 0.005
TP_PCT = 0.01
MAX_AJE = 120
HOSTS = ["https://data-api.binance.vision", "https://api.binance.com"]
FICHYE = "state.json"

app = Flask(__name__)
lock = threading.Lock()
premye = set()
eta = {"mache": {}, "pozisyon": {}, "istwa": [], "stat": {"gen": 0, "pet": 0},
       "dernye": {}, "update": "", "kont": 0}

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

def jwenn_done(sym):
    dènye_erè = None
    for h in HOSTS:
        try:
            url = h + "/api/v3/klines?symbol=" + sym + "&interval=1m&limit=100"
            done = json.loads(urlopen(url, timeout=10).read())
            return [k[0] for k in done], [float(k[4]) for k in done]
        except Exception as e:
            dènye_erè = e
    raise dènye_erè

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
    eta["istwa"].insert(0, {"id": eta["kont"], "tip": tip, "sym": sym,
                            "sans": sans, "le": le, "liy": liy})
    del eta["istwa"][50:]

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
        "Antre: " + str(round(p["antre"], 4)) + " | Soti: " + str(round(pri, 4)),
        "Rezilta: " + rez + " " + str(round(pl, 2)) + "%",
        "MT5: fèmen trade a kounye a"], le)

def louvri(sym, siyal, pri, r, le):
    if siyal == "ACHTE":
        sl, tp = pri * (1 - SL_PCT), pri * (1 + TP_PCT)
    else:
        sl, tp = pri * (1 + SL_PCT), pri * (1 - TP_PCT)
    eta["pozisyon"][sym] = {"sans": siyal, "antre": pri, "sl": sl, "tp": tp}
    evenman("ANTRE", sym, siyal, [
        siyal + " @ " + str(round(pri, 4)) + " | RSI " + str(round(r)),
        "MT5 -> SL: " + str(round(sl, 4)) + " | TP: " + str(round(tp, 4)),
        "Pocket Option -> ekspirasyon: 1 a 3 min"], le)

def trete(sym, siyal, a, b, r, pri, tan, le):
    if sym in eta["pozisyon"]:
        p = eta["pozisyon"][sym]
        if p["sans"] == "ACHTE":
            if pri <= p["sl"]:
                femen(sym, pri, "SL touche", le)
            elif pri >= p["tp"]:
                femen(sym, pri, "TP touche", le)
        else:
            if pri >= p["sl"]:
                femen(sym, pri, "SL touche", le)
            elif pri <= p["tp"]:
                femen(sym, pri, "TP touche", le)
    if sym not in premye:
        premye.add(sym)
        if siyal != "ATANN":
            eta["dernye"][sym] = tan[-2]
    elif siyal != "ATANN" and eta["dernye"].get(sym) != tan[-2]:
        eta["dernye"][sym] = tan[-2]
        fre = (time.time() * 1000 - (tan[-2] + 60000)) <= MAX_AJE * 1000
        if fre:
            if sym in eta["pozisyon"] and eta["pozisyon"][sym]["sans"] != siyal:
                femen(sym, pri, "Kwazman kontrè", le)
            if sym not in eta["pozisyon"]:
                louvri(sym, siyal, pri, r, le)
    p = eta["pozisyon"].get(sym)
    trade = None
    if p:
        trade = {"sans": p["sans"], "antre": p["antre"], "sl": p["sl"],
                 "tp": p["tp"], "pl": round(pl_pct(p, pri), 2)}
    eta["mache"][sym] = {"pri": pri, "tandans": "monte" if a > b else "desann",
                         "rsi": round(r), "trade": trade}

def boukle():
    while True:
        le = datetime.now().strftime("%H:%M:%S")
        for sym in PEZ:
            try:
                tan, prix = jwenn_done(sym)
                siyal, a, b, r = kalkile(prix)
                with lock:
                    trete(sym, siyal, a, b, r, prix[-1], tan, le)
            except Exception as e:
                with lock:
                    eta["mache"][sym] = {"err": str(e)[:80]}
        with lock:
            eta["update"] = le
            sove()
        time.sleep(PAUS)

threading.Thread(target=boukle, daemon=True).start()

PAJ = r"""<!doctype html><html lang="ht"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#0b0f14">
<link rel="manifest" href="/manifest.json">
<link rel="icon" href="/icon.svg"><link rel="apple-touch-icon" href="/icon.svg">
<meta name="apple-mobile-web-app-capable" content="yes">
<title>NPG Pocket Bot</title>
<style>
body{margin:0;padding:12px;background:#0b0f14;color:#e5e7eb;font-family:sans-serif}
h1{font-size:20px;margin:4px 0}
#st{font-size:12px;color:#9ca3af;margin-bottom:8px}
button{background:#1f2937;color:#fff;border:0;border-radius:8px;padding:8px 12px;margin-bottom:10px}
.kat{background:#111827;border-radius:10px;padding:10px;margin-bottom:8px}
.ev{background:#111827;border-radius:10px;padding:10px;margin-bottom:8px;font-size:14px;border-left:5px solid #6b7280}
.ev.achte{border-color:#22c55e}.ev.vann{border-color:#ef4444}.ev.soti{border-color:#f59e0b}
.achte{color:#22c55e;font-weight:bold}.vann{color:#ef4444;font-weight:bold}.atann{color:#9ca3af}
h2{font-size:16px;margin:14px 0 6px}
</style></head><body>
<h1>NPG POCKET BOT</h1><div id="st">Ap chaje...</div>
<button onclick="nt()">Aktive notifikasyon</button>
<h2>Mache a</h2><div id="mc"></div>
<h2>Siyal yo</h2><div id="ev"></div>
<script>
let dernyeId = null;
const esc = s => String(s).replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
function nt(){ if ('Notification' in window) Notification.requestPermission(); }
async function chaje(){
  const st = document.getElementById('st');
  try{
    const d = await (await fetch('/api/state')).json();
    st.textContent = 'Mizajou: ' + d.update + ' | GEN ' + d.stat.gen + ' / PET ' + d.stat.pet;
    let h = '';
    for (const [sym, m] of Object.entries(d.mache)){
      if (m.err){ h += `<div class="kat"><b>${esc(sym)}</b> erè rezo</div>`; continue; }
      let b = '<span class="atann">ATANN</span>';
      if (m.trade){
        b = `<span class="${m.trade.sans=='ACHTE'?'achte':'vann'}">TRADE ${m.trade.sans} | P/L ${m.trade.pl}%</span>`;
      }
      h += `<div class="kat"><b>${esc(sym)}</b> ${m.pri}<br>Mache a ap ${m.tandans} | RSI ${m.rsi}<br>${b}</div>`;
    }
    document.getElementById('mc').innerHTML = h;
    let e = '';
    for (const x of d.istwa){
      const k = x.tip=='ANTRE' ? (x.sans=='ACHTE'?'achte':'vann') : 'soti';
      e += `<div class="ev ${k}"><b>${x.le} ${esc(x.sym)} - ${x.tip}</b><br>${x.liy.map(esc).join('<br>')}</div>`;
    }
    document.getElementById('ev').innerHTML = e || '<p class="atann">Pa gen siyal ankò.</p>';
    if (d.istwa.length){
      const id = d.istwa[0].id;
      if (dernyeId !== null && id > dernyeId){
        if (navigator.vibrate) navigator.vibrate(300);
        if ('Notification' in window && Notification.permission == 'granted'){
          const x = d.istwa[0];
          new Notification(x.sym + ' ' + x.tip, {body: x.liy[0]});
        }
      }
      dernyeId = id;
    } else if (dernyeId === null){ dernyeId = 0; }
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

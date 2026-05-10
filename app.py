"""
XRP Tracker — Flask server (Render deployment)

Existing routes preserved exactly:
  GET  /                     → serves index.html  (Volume Tracker — UNCHANGED)
  GET  /proxy/coinone/<sym>  → Coinone CORS proxy (UNCHANGED)

New routes added:
  GET  /buysell              → serves buysell.html (Buy/Sell Pressure tab)
  GET  /api/buysell          → JSON: real-time buy/sell data for 7 exchanges
"""

from flask import Flask, jsonify, send_from_directory
import requests
import datetime
import pytz
import os

app = Flask(__name__, static_folder=".")

# ── existing: Coinone CORS proxy (UNCHANGED) ─────────────────────

COINONE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; XRP-Tracker/2.0)",
    "Accept": "application/json",
    "Referer": "https://coinone.co.kr/",
}

@app.route("/proxy/coinone/<symbol>")
def coinone_proxy(symbol):
    symbol = symbol.upper()
    try:
        url = f"https://api.coinone.co.kr/public/v2/chart/KRW/{symbol}?period=1d&size=365"
        resp = requests.get(url, headers=COINONE_HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        response = jsonify(data)
    except Exception as e:
        response = jsonify({"error": str(e), "chart": []})
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response


# ── existing: serve index.html (UNCHANGED) ───────────────────────

@app.route("/")
def index():
    return send_from_directory(".", "index.html")


# ── NEW: serve buysell.html ──────────────────────────────────────

@app.route("/buysell")
def buysell():
    return send_from_directory(".", "buysell.html")


# ── NEW: /api/buysell — real-time buy/sell JSON ──────────────────

def _get_krw_rate():
    for url, parser in [
        ("https://api.upbit.com/v1/ticker?markets=KRW-USDT",
         lambda r: float(r.json()[0]["trade_price"])),
        ("https://api.bithumb.com/public/ticker/USDT_KRW",
         lambda r: float(r.json()["data"]["closing_price"])),
    ]:
        try:
            return parser(requests.get(url, timeout=5))
        except:
            pass
    return 1350.0

def _kraken():
    try:
        t = requests.get("https://api.kraken.com/0/public/Ticker",
                         params={"pair": "XXRPZUSD"}, timeout=5).json()
        price = float(t["result"]["XXRPZUSD"]["c"][0])
        tr = requests.get("https://api.kraken.com/0/public/Trades",
                          params={"pair": "XXRPZUSD"}, timeout=5).json()
        trades = tr["result"]["XXRPZUSD"]
        today = datetime.datetime.utcnow().date()
        daily = [x for x in trades
                 if datetime.datetime.utcfromtimestamp(x[2]).date() == today]
        return price, sum(float(x[1]) for x in daily if x[3]=="b"), \
                      sum(float(x[1]) for x in daily if x[3]=="s")
    except: return None, 0, 0

def _binance_us():
    try:
        t = requests.get("https://api.binance.us/api/v3/ticker/price",
                         params={"symbol": "XRPUSD"}, timeout=5).json()
        price = float(t["price"])
        tr = requests.get("https://api.binance.us/api/v3/trades",
                          params={"symbol": "XRPUSD", "limit": 1000}, timeout=5).json()
        today = datetime.datetime.utcnow().date()
        daily = [x for x in tr
                 if datetime.datetime.utcfromtimestamp(x["time"]/1000).date() == today]
        return price, sum(float(x["qty"]) for x in daily if not x["isBuyerMaker"]), \
                      sum(float(x["qty"]) for x in daily if x["isBuyerMaker"])
    except: return None, 0, 0

def _coinbase():
    try:
        h = {"User-Agent": "Python/XRP-Tracker"}
        t = requests.get("https://api.exchange.coinbase.com/products/XRP-USD/ticker",
                         headers=h, timeout=5).json()
        price = float(t["price"])
        tr = requests.get("https://api.exchange.coinbase.com/products/XRP-USD/trades",
                          headers=h, timeout=5).json()
        return price, sum(float(x["size"]) for x in tr if x["side"]=="buy"), \
                      sum(float(x["size"]) for x in tr if x["side"]=="sell")
    except: return None, 0, 0

def _upbit(krw_rate):
    try:
        t = requests.get("https://api.upbit.com/v1/ticker",
                         params={"markets": "KRW-XRP"}, timeout=5).json()
        price_krw = float(t[0]["trade_price"])
        tr = requests.get("https://api.upbit.com/v1/trades/ticks",
                          params={"market": "KRW-XRP", "count": 100}, timeout=5).json()
        buy  = sum(float(x["trade_volume"]) for x in tr if x["ask_bid"]=="BID")
        sell = sum(float(x["trade_volume"]) for x in tr if x["ask_bid"]=="ASK")
        return price_krw / krw_rate, buy, sell, price_krw
    except: return None, 0, 0, 0

def _bitstamp():
    try:
        t = requests.get("https://www.bitstamp.net/api/v2/ticker/xrpusd/",
                         timeout=5).json()
        price = float(t["last"])
        tr = requests.get("https://www.bitstamp.net/api/v2/transactions/xrpusd/",
                          params={"time": "hour"}, timeout=5).json()
        return price, sum(float(x["amount"]) for x in tr if x["type"]=="0"), \
                      sum(float(x["amount"]) for x in tr if x["type"]=="1")
    except: return None, 0, 0

def _okx():
    try:
        t = requests.get("https://www.okx.com/api/v5/market/ticker",
                         params={"instId": "XRP-USDT"}, timeout=5).json()
        price = float(t["data"][0]["last"])
        tr = requests.get("https://www.okx.com/api/v5/market/trades",
                          params={"instId": "XRP-USDT", "limit": 500}, timeout=5).json()
        return price, sum(float(x["sz"]) for x in tr["data"] if x["side"]=="buy"), \
                      sum(float(x["sz"]) for x in tr["data"] if x["side"]=="sell")
    except: return None, 0, 0

def _gemini():
    try:
        t = requests.get("https://api.gemini.com/v1/pubticker/xrpusd",
                         timeout=5).json()
        price = float(t["last"])
        tr = requests.get("https://api.gemini.com/v1/trades/xrpusd",
                          params={"limit_trades": 500}, timeout=5).json()
        return price, sum(float(x["amount"]) for x in tr if x["type"]=="buy"), \
                      sum(float(x["amount"]) for x in tr if x["type"]=="sell")
    except: return None, 0, 0


@app.route("/api/buysell")
def api_buysell():
    krw_rate = _get_krw_rate()
    now = datetime.datetime.now(pytz.utc).astimezone(pytz.timezone("America/Los_Angeles"))

    kraken_p,   kraken_b,   kraken_s         = _kraken()
    binance_p,  binance_b,  binance_s         = _binance_us()
    coinbase_p, coinbase_b, coinbase_s        = _coinbase()
    upbit_p,    upbit_b,    upbit_s,  _       = _upbit(krw_rate)
    bitstamp_p, bitstamp_b, bitstamp_s        = _bitstamp()
    okx_p,      okx_b,      okx_s            = _okx()
    gemini_p,   gemini_b,   gemini_s          = _gemini()

    usd_prices = [p for p in [kraken_p, binance_p, coinbase_p] if p]
    kimchi = None
    if usd_prices and upbit_p:
        avg = sum(usd_prices) / len(usd_prices)
        kimchi = ((upbit_p - avg) / avg) * 100

    return jsonify({
        "timestamp": now.strftime("%I:%M:%S %p %Z"),
        "krw_rate": krw_rate,
        "kimchi": kimchi,
        "exchanges": [
            {"name": "Kraken",     "emoji": "🔷", "price": kraken_p,   "buy": kraken_b,   "sell": kraken_s},
            {"name": "Binance.US", "emoji": "🟡", "price": binance_p,  "buy": binance_b,  "sell": binance_s},
            {"name": "Coinbase",   "emoji": "🔵", "price": coinbase_p, "buy": coinbase_b, "sell": coinbase_s},
            {"name": "Upbit",      "emoji": "🇰🇷", "price": upbit_p,    "buy": upbit_b,    "sell": upbit_s},
            {"name": "Bitstamp",   "emoji": "🟢", "price": bitstamp_p, "buy": bitstamp_b, "sell": bitstamp_s},
            {"name": "OKX",        "emoji": "🟣", "price": okx_p,      "buy": okx_b,      "sell": okx_s},
            {"name": "Gemini",     "emoji": "💎", "price": gemini_p,   "buy": gemini_b,   "sell": gemini_s},
        ],
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=False)

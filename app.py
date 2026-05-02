from flask import Flask, make_response, send_from_directory, abort
import requests
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, 'static')

app = Flask(__name__, static_folder=STATIC_DIR)

# ── Coinone proxy ──────────────────────────────────────────────
# Coinone blocks browser fetches (no CORS headers).
# This route calls Coinone server-side (no CORS restriction) and
# re-serves the JSON with Access-Control-Allow-Origin: * so the
# dashboard JS can read it.
COINONE_BASE = 'https://api.coinone.co.kr/public/v2'
ALLOWED_SYMBOLS = {'XRP', 'BTC', 'ETH', 'RLUSD', 'SOL', 'ADA', 'DOT'}

@app.route('/proxy/coinone/<symbol>')
def proxy_coinone(symbol):
    symbol = symbol.upper()
    if symbol not in ALLOWED_SYMBOLS:
        abort(400, f'Symbol {symbol} not in allowlist')
    try:
        r = requests.get(
            f'{COINONE_BASE}/chart/KRW/{symbol}',
            params={'interval': '1D'},
            timeout=15,
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        r.raise_for_status()
        resp = make_response(r.content)
        resp.headers['Access-Control-Allow-Origin'] = '*'
        resp.headers['Content-Type'] = 'application/json'
        return resp
    except requests.exceptions.Timeout:
        abort(504, 'Coinone timed out')
    except requests.exceptions.HTTPError as e:
        abort(502, f'Coinone error: {e}')
    except Exception as e:
        abort(500, str(e))


# ── Serve the dashboard ────────────────────────────────────────
@app.route('/')
def index():
    return send_from_directory(STATIC_DIR, 'index.html')

@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory(STATIC_DIR, filename)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

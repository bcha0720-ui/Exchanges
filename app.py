from flask import Flask, make_response, send_from_directory, abort
import requests
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)

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


@app.route('/')
def index():
    return send_from_directory(BASE_DIR, 'index.html')


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

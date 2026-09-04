"""
Datos públicos de mercado (sin API key). Preparado para correr desde GitHub Actions (IPs de EE.UU.):
- precio y volumen: espejo público de Binance (data-api.binance.vision), no geobloqueado
- funding rate, open interest, ratio long/short: Bybit v5 (API pública accesible desde EE.UU.)
"""
import time
import requests

SPOT = "https://data-api.binance.vision"
BYBIT = "https://api.bybit.com"


def _get(url, params=None, retries=3):
    for i in range(retries):
        try:
            r = requests.get(url, params=params, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception:
            if i == retries - 1:
                raise
            time.sleep(2)


def plain(symbol):
    return symbol.replace("/", "")


def klines(symbol, interval="15m", limit=96):
    data = _get(f"{SPOT}/api/v3/klines", {"symbol": plain(symbol), "interval": interval, "limit": limit})
    return [
        {"t": k[0], "o": float(k[1]), "h": float(k[2]), "l": float(k[3]), "c": float(k[4]),
         "v": float(k[5]), "taker_buy": float(k[9])}
        for k in data
    ]


def price(symbol):
    return float(_get(f"{SPOT}/api/v3/ticker/price", {"symbol": plain(symbol)})["price"])


def funding(symbol, limit=6):
    d = _get(f"{BYBIT}/v5/market/funding-history",
             {"category": "linear", "symbol": plain(symbol), "limit": limit})
    rows = d["result"]["list"]
    return [float(x["fundingRate"]) for x in reversed(rows)]


def open_interest_hist(symbol, limit=24):
    d = _get(f"{BYBIT}/v5/market/open-interest",
             {"category": "linear", "symbol": plain(symbol), "intervalTime": "1h", "limit": limit})
    rows = d["result"]["list"]
    return [float(x["openInterest"]) for x in reversed(rows)]


def long_short_ratio(symbol, limit=6):
    d = _get(f"{BYBIT}/v5/market/account-ratio",
             {"category": "linear", "symbol": plain(symbol), "period": "1h", "limit": limit})
    rows = d["result"]["list"]
    return [float(x["buyRatio"]) / max(float(x["sellRatio"]), 1e-9) for x in reversed(rows)]


def snapshot(symbol):
    """Resumen numérico compacto para pasar al modelo."""
    ks = klines(symbol)
    closes = [k["c"] for k in ks]
    vols = [k["v"] for k in ks]
    taker = [k["taker_buy"] / k["v"] if k["v"] else 0.5 for k in ks]

    def pct(a, b):
        return (b - a) / a * 100 if a else 0.0

    now = closes[-1]
    snap = {
        "price": now,
        "chg_1h_pct": round(pct(closes[-5], now), 3),
        "chg_4h_pct": round(pct(closes[-17], now), 3),
        "chg_24h_pct": round(pct(closes[0], now), 3),
        "high_24h": max(k["h"] for k in ks),
        "low_24h": min(k["l"] for k in ks),
        "vol_last_1h_vs_avg": round(sum(vols[-4:]) / 4 / (sum(vols) / len(vols)), 3),
        "taker_buy_ratio_1h": round(sum(taker[-4:]) / 4, 3),
        "taker_buy_ratio_24h": round(sum(taker) / len(taker), 3),
    }
    try:
        f = funding(symbol)
        snap["funding_last"] = f[-1]
        snap["funding_avg_6"] = round(sum(f) / len(f), 6)
    except Exception as e:
        snap["funding_error"] = str(e)[:80]
    try:
        oi = open_interest_hist(symbol)
        snap["oi_chg_4h_pct"] = round(pct(oi[-5], oi[-1]), 3)
        snap["oi_chg_24h_pct"] = round(pct(oi[0], oi[-1]), 3)
    except Exception as e:
        snap["oi_error"] = str(e)[:80]
    try:
        ls = long_short_ratio(symbol)
        snap["long_short_ratio"] = round(ls[-1], 3)
        snap["long_short_trend"] = round(ls[-1] - ls[0], 3)
    except Exception as e:
        snap["ls_error"] = str(e)[:80]
    return snap

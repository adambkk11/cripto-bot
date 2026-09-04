"""
Recoge datos públicos de Binance (no requiere API key):
- precio y volumen (spot, velas 15m)
- funding rate (futuros perpetuos)
- open interest y su variación
- ratio long/short de grandes cuentas
- volumen taker buy vs sell
"""
import time
import requests

SPOT = "https://api.binance.com"
FUT = "https://fapi.binance.com"


def _get(url, params=None, retries=3):
    for i in range(retries):
        try:
            r = requests.get(url, params=params, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if i == retries - 1:
                raise
            time.sleep(2)


def fut_symbol(symbol):
    return symbol.replace("/", "")


def klines(symbol, interval="15m", limit=96):
    data = _get(f"{SPOT}/api/v3/klines", {"symbol": fut_symbol(symbol), "interval": interval, "limit": limit})
    return [
        {"t": k[0], "o": float(k[1]), "h": float(k[2]), "l": float(k[3]), "c": float(k[4]),
         "v": float(k[5]), "taker_buy": float(k[9])}
        for k in data
    ]


def price(symbol):
    return float(_get(f"{SPOT}/api/v3/ticker/price", {"symbol": fut_symbol(symbol)})["price"])


def funding(symbol, limit=6):
    data = _get(f"{FUT}/fapi/v1/fundingRate", {"symbol": fut_symbol(symbol), "limit": limit})
    return [float(d["fundingRate"]) for d in data]


def open_interest_hist(symbol, period="1h", limit=24):
    data = _get(f"{FUT}/futures/data/openInterestHist",
                {"symbol": fut_symbol(symbol), "period": period, "limit": limit})
    return [float(d["sumOpenInterestValue"]) for d in data]


def long_short_ratio(symbol, period="1h", limit=6):
    data = _get(f"{FUT}/futures/data/topLongShortAccountRatio",
                {"symbol": fut_symbol(symbol), "period": period, "limit": limit})
    return [float(d["longShortRatio"]) for d in data]


def snapshot(symbol):
    """Devuelve un resumen numérico compacto para pasar al modelo."""
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
    except Exception:
        pass
    try:
        oi = open_interest_hist(symbol)
        snap["oi_chg_4h_pct"] = round(pct(oi[-5], oi[-1]), 3)
        snap["oi_chg_24h_pct"] = round(pct(oi[0], oi[-1]), 3)
    except Exception:
        pass
    try:
        ls = long_short_ratio(symbol)
        snap["top_long_short_ratio"] = ls[-1]
        snap["top_long_short_trend"] = round(ls[-1] - ls[0], 3)
    except Exception:
        pass
    return snap

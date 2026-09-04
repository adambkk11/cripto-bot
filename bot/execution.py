"""
Dos brokers con la misma interfaz:
  PaperBroker  -> simula con comisión y slippage, guarda saldo en la base de datos
  BinanceBroker -> spot real vía ccxt (solo compra/vende, sin apalancamiento)
Spot: solo podemos estar en cash (USDT) o en el activo. "sell" con posición abierta = cerrar.
"""
from . import config


class PaperBroker:
    def __init__(self, ledger):
        self.ledger = ledger
        st = ledger.get_state()
        self.cash = st["cash"]
        self.qty = st["qty"]
        self.entry = st["entry"]

    def _save(self):
        self.ledger.set_state(self.cash, self.qty, self.entry)

    def equity(self, price):
        return self.cash + self.qty * price

    def position(self, price):
        if self.qty <= 0:
            return None
        return {"qty": self.qty, "entry": self.entry, "pnl_pct": round((price - self.entry) / self.entry * 100, 3)}

    def buy(self, price, amount_quote):
        fill = price * (1 + config.SLIPPAGE)
        fee = amount_quote * config.FEE_RATE
        qty = (amount_quote - fee) / fill
        self.cash -= amount_quote
        self.qty += qty
        self.entry = fill
        self._save()
        return {"side": "buy", "price": fill, "qty": qty, "fee": fee}

    def sell_all(self, price):
        fill = price * (1 - config.SLIPPAGE)
        gross = self.qty * fill
        fee = gross * config.FEE_RATE
        self.cash += gross - fee
        qty = self.qty
        self.qty = 0.0
        self.entry = 0.0
        self._save()
        return {"side": "sell", "price": fill, "qty": qty, "fee": fee}


class BinanceBroker:
    def __init__(self, ledger):
        import ccxt
        self.ledger = ledger
        self.ex = ccxt.binance({
            "apiKey": config.BINANCE_API_KEY,
            "secret": config.BINANCE_SECRET,
            "enableRateLimit": True,
        })
        self.base, self.quote = config.SYMBOL.split("/")
        st = ledger.get_state()
        self.entry = st["entry"]

    def _balances(self):
        b = self.ex.fetch_balance()
        return float(b["free"].get(self.quote, 0)), float(b["free"].get(self.base, 0))

    def equity(self, price):
        cash, qty = self._balances()
        return cash + qty * price

    def position(self, price):
        _, qty = self._balances()
        if qty * price < 5:  # polvo, no cuenta
            return None
        if not self.entry:
            self.entry = price
        return {"qty": qty, "entry": self.entry, "pnl_pct": round((price - self.entry) / self.entry * 100, 3)}

    def buy(self, price, amount_quote):
        order = self.ex.create_order(config.SYMBOL, "market", "buy", None, None, {"quoteOrderQty": round(amount_quote, 2)})
        fill = float(order.get("average") or price)
        qty = float(order.get("filled") or amount_quote / fill)
        fee = sum(float(f.get("cost", 0)) for f in order.get("fees", []) or [])
        self.entry = fill
        cash, q = self._balances()
        self.ledger.set_state(cash, q, self.entry)
        return {"side": "buy", "price": fill, "qty": qty, "fee": fee}

    def sell_all(self, price):
        _, qty = self._balances()
        qty = float(self.ex.amount_to_precision(config.SYMBOL, qty))
        order = self.ex.create_order(config.SYMBOL, "market", "sell", qty)
        fill = float(order.get("average") or price)
        fee = sum(float(f.get("cost", 0)) for f in order.get("fees", []) or [])
        self.entry = 0.0
        cash, q = self._balances()
        self.ledger.set_state(cash, q, 0.0)
        return {"side": "sell", "price": fill, "qty": qty, "fee": fee}


def make_broker(ledger):
    return BinanceBroker(ledger) if config.MODE == "real" else PaperBroker(ledger)

"""
Guarda TODO: cada evaluación (aunque no opere), cada operación con su tesis,
el saldo y el benchmark buy-and-hold. Sin esto no hay forma de saber si funciona.
"""
import sqlite3
import time
from . import config


class Ledger:
    def __init__(self):
        self.db = sqlite3.connect(config.DB_PATH)
        self.db.row_factory = sqlite3.Row
        self._init()

    def _init(self):
        c = self.db.cursor()
        c.executescript("""
        CREATE TABLE IF NOT EXISTS state (k TEXT PRIMARY KEY, v REAL);
        CREATE TABLE IF NOT EXISTS decisions (
            id INTEGER PRIMARY KEY, ts INTEGER, price REAL,
            p_up REAL, p_down REAL, action TEXT, thesis TEXT,
            executed INTEGER, equity REAL, benchmark REAL, snapshot TEXT
        );
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY, ts INTEGER, side TEXT, price REAL, qty REAL,
            fee REAL, reason TEXT, p_up REAL, thesis TEXT, equity_after REAL,
            pnl_pct REAL
        );
        """)
        self.db.commit()
        if self._get("cash") is None:
            self._set("cash", config.START_BALANCE)
            self._set("qty", 0.0)
            self._set("entry", 0.0)
            self._set("start_ts", time.time())

    def _get(self, k):
        r = self.db.execute("SELECT v FROM state WHERE k=?", (k,)).fetchone()
        return r["v"] if r else None

    def _set(self, k, v):
        self.db.execute("INSERT OR REPLACE INTO state(k,v) VALUES(?,?)", (k, v))
        self.db.commit()

    def get_state(self):
        return {"cash": self._get("cash"), "qty": self._get("qty"), "entry": self._get("entry")}

    def set_state(self, cash, qty, entry):
        self._set("cash", cash); self._set("qty", qty); self._set("entry", entry)

    # --- benchmark: qué habría pasado comprando el día 1 y no tocando nada ---
    def benchmark(self, price):
        p0 = self._get("bench_price0")
        if p0 is None:
            self._set("bench_price0", price)
            p0 = price
        return config.START_BALANCE * (1 - config.FEE_RATE) * price / p0

    def last_trade_ts(self):
        r = self.db.execute("SELECT MAX(ts) AS t FROM trades").fetchone()
        return r["t"] or 0

    def log_decision(self, price, sig, executed, equity, bench, snapshot):
        self.db.execute(
            "INSERT INTO decisions(ts,price,p_up,p_down,action,thesis,executed,equity,benchmark,snapshot)"
            " VALUES(?,?,?,?,?,?,?,?,?,?)",
            (int(time.time()), price, sig["p_up"], sig["p_down"], sig["action"], sig["thesis"],
             int(executed), equity, bench, str(snapshot)))
        self.db.commit()

    def log_trade(self, fill, reason, sig, equity_after, pnl_pct=None):
        self.db.execute(
            "INSERT INTO trades(ts,side,price,qty,fee,reason,p_up,thesis,equity_after,pnl_pct)"
            " VALUES(?,?,?,?,?,?,?,?,?,?)",
            (int(time.time()), fill["side"], fill["price"], fill["qty"], fill["fee"], reason,
             sig["p_up"] if sig else None, sig["thesis"] if sig else None, equity_after, pnl_pct))
        self.db.commit()

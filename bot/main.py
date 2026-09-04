"""
Bucle principal. Corre 24/7:
  1. recoge datos
  2. si hay posición: comprueba stop-loss / take-profit / tiempo máximo
  3. pide señal al modelo (probabilidad + tesis)
  4. opera solo si la probabilidad supera THRESHOLD
  5. registra todo
  6. kill-switch: si el saldo baja de KILL_SWITCH_BALANCE, cierra todo y se apaga
"""
import os
import sys
import time
import traceback
from . import config, collectors, signal as sig_mod, notify
from .ledger import Ledger
from .execution import make_broker


def run_once():
    """Un ciclo y salir (modo GitHub Actions). El estado vive en ledger.db, que se commitea."""
    ledger = Ledger()
    broker = make_broker(ledger)
    tick(ledger, broker)


def run():
    ledger = Ledger()
    broker = make_broker(ledger)
    notify.send(f"🤖 Bot arrancado | {config.MODE.upper()} | {config.SYMBOL} | "
                f"umbral {config.THRESHOLD} | kill-switch {config.KILL_SWITCH_BALANCE}")

    while True:
        try:
            tick(ledger, broker)
        except SystemExit:
            raise
        except Exception:
            notify.send("⚠️ Error en ciclo:\n" + traceback.format_exc()[-800:])
        time.sleep(config.INTERVAL_SECONDS)


def tick(ledger, broker):
    if os.path.exists("KILLED"):
        print("Bot apagado por kill-switch. Borra el archivo KILLED del repo para reactivarlo.")
        return
    snap = collectors.snapshot(config.SYMBOL)
    price = snap["price"]
    equity = broker.equity(price)
    bench = ledger.benchmark(price)
    pos = broker.position(price)

    # --- kill switch ---
    if equity < config.KILL_SWITCH_BALANCE:
        if pos:
            fill = broker.sell_all(price)
            ledger.log_trade(fill, "kill_switch", None, broker.equity(price), pos["pnl_pct"])
        notify.send(f"🛑 KILL-SWITCH. Saldo {equity:.2f} < {config.KILL_SWITCH_BALANCE}. "
                    f"Benchmark hubiera sido {bench:.2f}. Bot apagado.")
        open("KILLED", "w").write(time.strftime("%Y-%m-%d %H:%M"))
        sys.exit(0)

    # --- salidas mecánicas de la posición abierta (no consultan al modelo) ---
    if pos:
        held_h = (time.time() - ledger.last_trade_ts()) / 3600
        reason = None
        if pos["pnl_pct"] <= -config.STOP_LOSS_PCT * 100:
            reason = "stop_loss"
        elif pos["pnl_pct"] >= config.TAKE_PROFIT_PCT * 100:
            reason = "take_profit"
        elif held_h >= config.MAX_HOLD_HOURS:
            reason = "max_hold"
        if reason:
            fill = broker.sell_all(price)
            eq = broker.equity(price)
            ledger.log_trade(fill, reason, None, eq, pos["pnl_pct"])
            notify.send(f"📤 Cierre por {reason} a {fill['price']:.2f} | PnL {pos['pnl_pct']:+.2f}% | "
                        f"saldo {eq:.2f} (bench {bench:.2f})")
            pos = None

    # --- señal del modelo ---
    sig = sig_mod.get_signal(snap, pos)
    executed = False
    cooldown_ok = (time.time() - ledger.last_trade_ts()) >= config.MIN_SECONDS_BETWEEN_TRADES

    if not pos and sig["p_up"] >= config.THRESHOLD and cooldown_ok:
        amount = broker.equity(price) * config.POSITION_PCT
        if amount >= 10:  # mínimo de Binance spot
            fill = broker.buy(price, amount)
            executed = True
            ledger.log_trade(fill, "signal_buy", sig, broker.equity(price))
            notify.send(f"📥 COMPRA {amount:.2f} USDT a {fill['price']:.2f} | p_up {sig['p_up']}\n{sig['thesis']}")

    elif pos and sig["p_down"] >= config.THRESHOLD and cooldown_ok:
        fill = broker.sell_all(price)
        executed = True
        eq = broker.equity(price)
        ledger.log_trade(fill, "signal_sell", sig, eq, pos["pnl_pct"])
        notify.send(f"📤 VENTA a {fill['price']:.2f} | PnL {pos['pnl_pct']:+.2f}% | p_down {sig['p_down']} | "
                    f"saldo {eq:.2f} (bench {bench:.2f})\n{sig['thesis']}")

    ledger.log_decision(price, sig, executed, broker.equity(price), bench, snap)
    print(f"[{time.strftime('%H:%M:%S')}] {price:.2f} | up {sig['p_up']} down {sig['p_down']} | "
          f"{'OP' if executed else '--'} | eq {broker.equity(price):.2f} bench {bench:.2f}", flush=True)


if __name__ == "__main__":
    if "--once" in sys.argv:
        run_once()
    else:
        run()

"""
python report.py
Muestra: saldo vs benchmark, operaciones, win rate, comisiones pagadas,
y CALIBRACIÓN: cuando el modelo dijo 65%, ¿acertó el 65%?
"""
import sqlite3
import os
from collections import defaultdict

DB = os.getenv("DB_PATH", "ledger.db")
db = sqlite3.connect(DB)
db.row_factory = sqlite3.Row

last = db.execute("SELECT equity, benchmark FROM decisions ORDER BY id DESC LIMIT 1").fetchone()
n_dec = db.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
trades = db.execute("SELECT * FROM trades ORDER BY ts").fetchall()
closes = [t for t in trades if t["side"] == "sell" and t["pnl_pct"] is not None]
fees = sum(t["fee"] for t in trades)

print("=" * 50)
print(f"Evaluaciones: {n_dec} | Operaciones: {len(trades)} | Cierres: {len(closes)}")
if last:
    print(f"Saldo bot:   {last['equity']:.2f}")
    print(f"Benchmark:   {last['benchmark']:.2f}   (comprar día 1 y no tocar)")
    print(f"Diferencia:  {last['equity'] - last['benchmark']:+.2f}")
print(f"Comisiones pagadas: {fees:.2f}")
if closes:
    wins = [c for c in closes if c["pnl_pct"] > 0]
    print(f"Win rate: {len(wins)}/{len(closes)} = {len(wins)/len(closes)*100:.1f}%")
    print(f"PnL medio por cierre: {sum(c['pnl_pct'] for c in closes)/len(closes):+.2f}%")
    reasons = defaultdict(int)
    for c in closes:
        reasons[c["reason"]] += 1
    print("Motivos de cierre:", dict(reasons))

# --- calibración: p_up declarada vs subida real 4h después ---
print("\nCALIBRACIÓN (p_up declarada → % de veces que subió >0 en las 4h siguientes)")
rows = db.execute("SELECT ts, price, p_up FROM decisions ORDER BY ts").fetchall()
buckets = defaultdict(lambda: [0, 0])
for i, r in enumerate(rows):
    target = r["ts"] + 4 * 3600
    fut = next((x for x in rows[i + 1:] if x["ts"] >= target), None)
    if not fut:
        continue
    b = round(r["p_up"] * 10) / 10
    buckets[b][0] += 1
    buckets[b][1] += 1 if fut["price"] > r["price"] else 0
for b in sorted(buckets):
    n, up = buckets[b]
    print(f"  dijo {b:.1f} → subió {up/n*100:5.1f}%  (n={n})")
print("Si la columna derecha no sigue a la izquierda, el número del modelo es decorativo.")
print("=" * 50)

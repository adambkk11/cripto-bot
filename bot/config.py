import os
from dotenv import load_dotenv

load_dotenv()


def _f(name, default):
    return float(os.getenv(name, default))


MODE = os.getenv("MODE", "paper").lower()
SYMBOL = os.getenv("SYMBOL", "BTC/USDT")
START_BALANCE = _f("START_BALANCE", 100)

INTERVAL_SECONDS = int(_f("INTERVAL_SECONDS", 60))
MIN_SECONDS_BETWEEN_TRADES = int(_f("MIN_SECONDS_BETWEEN_TRADES", 900))

THRESHOLD = _f("THRESHOLD", 0.62)
POSITION_PCT = _f("POSITION_PCT", 0.25)
STOP_LOSS_PCT = _f("STOP_LOSS_PCT", 0.02)
TAKE_PROFIT_PCT = _f("TAKE_PROFIT_PCT", 0.03)
MAX_HOLD_HOURS = _f("MAX_HOLD_HOURS", 12)
KILL_SWITCH_BALANCE = _f("KILL_SWITCH_BALANCE", 70)
FEE_RATE = _f("FEE_RATE", 0.001)
SLIPPAGE = _f("SLIPPAGE", 0.0005)

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").lower()   # openai (Groq, Gemini, OpenRouter...) | anthropic
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
MODEL = os.getenv("MODEL", "llama-3.3-70b-versatile")

BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_SECRET = os.getenv("BINANCE_SECRET", "")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

DB_PATH = os.getenv("DB_PATH", "ledger.db")

assert MODE in ("paper", "real"), "MODE debe ser paper o real"
assert LLM_API_KEY, "Falta LLM_API_KEY"
if MODE == "real":
    assert BINANCE_API_KEY and BINANCE_SECRET, "MODE=real requiere BINANCE_API_KEY y BINANCE_SECRET"

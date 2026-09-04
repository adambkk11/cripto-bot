# cripto-bot

Bot que evalúa el mercado cada 10 minutos desde GitHub Actions, pide al modelo una probabilidad
de subida/bajada con su tesis, y opera solo cuando supera el umbral. Registra cada decisión,
compara contra buy-and-hold y se apaga solo si el saldo baja del kill-switch. Sin servidor.

## Montaje en GitHub (10 minutos)

1. Crea un repo **público** en GitHub llamado `cripto-bot` y sube esta carpeta entera.
2. Repo → Settings → Secrets and variables → Actions → pestaña **Secrets** → New repository secret:
   - `LLM_API_KEY` (obligatorio) — la clave del modelo. Ver "Modelo gratis" abajo.
   - `TELEGRAM_TOKEN` y `TELEGRAM_CHAT_ID` (opcional, avisos)
   - `BINANCE_API_KEY` y `BINANCE_SECRET` (solo para modo real)
3. Repo → Settings → Actions → General → Workflow permissions → marca **Read and write permissions** → Save.
4. Pestaña **Actions** → `cripto-bot` → **Run workflow**. Si la primera ejecución sale en verde, ya está: seguirá sola cada 10 min.

## Cambiar parámetros sin tocar código

Settings → Secrets and variables → Actions → pestaña **Variables** → New repository variable.
Cualquiera de estas (si no la creas, usa el valor por defecto):

| Variable | Por defecto | Qué hace |
|---|---|---|
| `MODE` | paper | `paper` o `real` |
| `SYMBOL` | BTC/USDT | Par a operar |
| `START_BALANCE` | 100 | Saldo inicial en paper |
| `THRESHOLD` | 0.62 | Solo opera si p_up / p_down supera esto |
| `POSITION_PCT` | 0.25 | % del saldo por operación |
| `STOP_LOSS_PCT` | 0.02 | Cierre automático si pierde 2% |
| `TAKE_PROFIT_PCT` | 0.03 | Cierre automático si gana 3% |
| `MAX_HOLD_HOURS` | 12 | Cierre automático por tiempo |
| `KILL_SWITCH_BALANCE` | 70 | Saldo por debajo del cual se apaga |
| `MIN_SECONDS_BETWEEN_TRADES` | 1800 | Mínimo entre operaciones |
| `LLM_PROVIDER` | openai | `openai` (Groq, Gemini, OpenRouter...) o `anthropic` |
| `LLM_BASE_URL` | https://api.groq.com/openai/v1 | Endpoint del proveedor |
| `MODEL` | llama-3.3-70b-versatile | Modelo |

## Ver resultados

Pestaña Actions → `report` → Run workflow → abre la ejecución y lee la salida.
Muestra saldo vs benchmark, operaciones, win rate, comisiones y calibración de las probabilidades.

## Pasar a real

1. Binance → API Management → Create API → activa **solo** "Enable Spot & Margin Trading". Sin retiradas.
2. Añade `BINANCE_API_KEY` y `BINANCE_SECRET` en Secrets.
3. Variable `MODE` = `real`.
4. Borra `ledger.db` del repo (para empezar limpio). Ten al menos 15 USDT en spot.

## Kill-switch

Si el saldo baja de `KILL_SWITCH_BALANCE`, el bot cierra la posición, crea un archivo `KILLED` en el repo
y deja de operar. Para reactivarlo: borra `KILLED` (y `ledger.db` si quieres empezar de cero).

## Pararlo a mano

Pestaña Actions → `cripto-bot` → menú `...` → Disable workflow. Si hay posición abierta, ciérrala en Binance.

## Modelo gratis

Por defecto usa **Groq** (Llama 3.3 70B), que tiene plan gratuito suficiente para 144 llamadas/día.
Clave en console.groq.com → API Keys. Métela como `LLM_API_KEY`. No hay que crear ninguna variable más.

Alternativas (cambia las Variables `LLM_BASE_URL` y `MODEL`):
- **Gemini** (Google, gratis): `https://generativelanguage.googleapis.com/v1beta/openai` + `gemini-2.0-flash`. Clave en aistudio.google.com.
- **OpenRouter** (modelos con sufijo `:free`): `https://openrouter.ai/api/v1`. Clave en openrouter.ai.
- **Anthropic** (de pago): `LLM_PROVIDER=anthropic`, `MODEL=claude-haiku-4-5-20251001`.

Los planes gratuitos cambian; si una ejecución falla con error 429 (rate limit), cambia de proveedor.

## Qué mirar a las 6-8 semanas

1. Saldo bot vs Benchmark. Si no lo bate, la estrategia no aporta.
2. Calibración: si "dijo 0.7" no sube ~70% de las veces, las probabilidades son decorativas.
3. Comisiones pagadas: lo único garantizado del sistema.

## Modo servidor (alternativa)

`python -m bot.main` sin `--once` corre en bucle continuo. Config en `.env` (ver `.env.example`).
Unidad systemd en `deploy/`.

"""
Pasa el snapshot numérico al modelo y obtiene:
  p_up, p_down (probabilidades para las próximas ~4-12h), action, thesis.
El modelo NO ejecuta nada: solo opina. La decisión final la toma main.py con el umbral.
"""
import json
import requests
from . import config

SYSTEM = """Eres un analista cuantitativo de criptomonedas. Recibes un resumen numérico del mercado
(precio, momentum, volumen, funding rate, open interest, posicionamiento de grandes cuentas, flujo taker).
Tu trabajo: estimar la probabilidad de que el precio suba o baje más de un 1.5% en las próximas 4-12 horas.

Reglas:
- Sé honesto con la incertidumbre. La mayoría del tiempo el mercado es ruido: p_up y p_down cerca de 0.5 es la respuesta correcta.
- Solo da probabilidades altas (>0.62) cuando varios indicadores independientes apunten en la misma dirección.
- Funding muy positivo + OI subiendo + ratio long/short alto = mercado sobreapalancado en largos (riesgo de liquidaciones a la baja). Y viceversa.
- Volumen alto con taker buy dominante confirma; volumen bajo debilita cualquier señal.
- Responde SOLO con JSON, sin texto antes ni después, sin backticks:
{"p_up": 0.00, "p_down": 0.00, "action": "buy|sell|hold", "thesis": "una o dos frases con los datos concretos que sustentan la estimación"}
p_up + p_down debe sumar 1.0."""


def _user_msg(snapshot, position):
    return (
        f"Símbolo: {config.SYMBOL}\n"
        f"Datos de mercado: {json.dumps(snapshot)}\n"
        f"Posición abierta actual: {json.dumps(position) if position else 'ninguna'}\n"
        "Devuelve el JSON."
    )


def _headers():
    return {"Authorization": f"Bearer {config.LLM_API_KEY}", "Content-Type": "application/json"}


def _pick_model():
    """Si el modelo configurado no existe, pregunta al proveedor cuáles hay y elige el mejor disponible."""
    r = requests.get(f"{config.LLM_BASE_URL.rstrip('/')}/models", headers=_headers(), timeout=30)
    r.raise_for_status()
    ids = [m["id"] for m in r.json().get("data", [])]
    prefs = ["70b", "405b", "120b", "maverick", "scout", "llama-4", "llama-3.3", "llama", "qwen", "mixtral", "gemma"]
    for key in prefs:
        for mid in ids:
            low = mid.lower()
            if key in low and "guard" not in low and "whisper" not in low and "tts" not in low and "vision" not in low:
                return mid
    return ids[0] if ids else config.MODEL


def _chat(model, user):
    return requests.post(
        f"{config.LLM_BASE_URL.rstrip('/')}/chat/completions",
        headers=_headers(),
        json={
            "model": model,
            "temperature": 0.2,
            "max_tokens": 2000,
            "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
        },
        timeout=60,
    )


def _call_openai_compat(user):
    r = _chat(config.MODEL, user)
    if r.status_code in (400, 404) and "model" in r.text.lower():
        alt = _pick_model()
        print(f"Modelo '{config.MODEL}' no disponible; usando '{alt}'. "
              f"Pon la Variable MODEL={alt} en GitHub para fijarlo.", flush=True)
        r = _chat(alt, user)
    if not r.ok:
        raise RuntimeError(f"Error del modelo {r.status_code}: {r.text[:300]}")
    return r.json()["choices"][0]["message"]["content"]


def _call_anthropic(user):
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": config.LLM_API_KEY, "anthropic-version": "2023-06-01",
                 "Content-Type": "application/json"},
        json={"model": config.MODEL, "max_tokens": 2000, "system": SYSTEM,
              "messages": [{"role": "user", "content": user}]},
        timeout=60,
    )
    r.raise_for_status()
    return "".join(b.get("text", "") for b in r.json()["content"])


def get_signal(snapshot, position):
    user = _user_msg(snapshot, position)
    text = _call_anthropic(user) if config.LLM_PROVIDER == "anthropic" else _call_openai_compat(user)
    text = text.strip().replace("```json", "").replace("```", "").strip()
    if "{" in text:
        text = text[text.index("{"): text.rindex("}") + 1]
    out = json.loads(text)
    p_up = float(out.get("p_up", 0.5))
    p_down = float(out.get("p_down", 1 - p_up))
    s = p_up + p_down
    if s > 0:
        p_up, p_down = p_up / s, p_down / s
    return {
        "p_up": round(p_up, 3),
        "p_down": round(p_down, 3),
        "action": out.get("action", "hold"),
        "thesis": str(out.get("thesis", ""))[:500],
    }

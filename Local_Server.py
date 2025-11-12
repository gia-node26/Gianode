# server.py — minimal API for your HTML GUI ↔ RTDB ↔ Ollama
import os, math, json
from typing import Optional
from fastapi import FastAPI, Query
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import firebase_admin
from firebase_admin import credentials, db
from langchain_ollama.llms import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate

# ---------- CONFIG ----------
RTDB_URL = "https://giatest-74d4a-default-rtdb.firebaseio.com"
SERVICE_ACCOUNT = os.environ.get(
    "GIA_SERVICE_ACCOUNT",
    r"C:\Users\jonca\gianode\Gia\LLM_GPT\service_account.json"
)
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")

# ---------- APP ----------
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],            # dev: open CORS so the HTML can call us
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Firebase init ----------
def init_rtdb():
    if not firebase_admin._apps:
        if SERVICE_ACCOUNT and os.path.exists(SERVICE_ACCOUNT):
            cred = credentials.Certificate(SERVICE_ACCOUNT)
            print(f"🔐 Using credential file: {SERVICE_ACCOUNT}")
        else:
            cred = credentials.ApplicationDefault()
            print("⚠️ Using Application Default Credentials")
        firebase_admin.initialize_app(cred, {"databaseURL": RTDB_URL})
        print("✅ Firebase initialized")

# ---------- Helpers ----------
def f_to_c(v):
    try:
        return (float(v) - 32.0) * (5.0 / 9.0) if v is not None else None
    except Exception:
        return None

def normalize_latest(raw: dict) -> dict:
    # RTDB fields from your ESP: hum (%), temp (°F), soil (%), light (lux), ts
    return {
        "moisture": raw.get("soil"),
        "temperature_c": f_to_c(raw.get("temp")),
        "humidity_pct": raw.get("hum"),
        "light_lux": raw.get("light"),
        "color_index": None,         # optional image feature
        "ec_mScm": None,
        "ph": None,
        "soil_temp_c": None,
        "growth_stage": "unknown",
    }

def feature_vector(d: dict) -> dict:
    def g(k, default=None): return d.get(k, default)
    def r(x, n):
        try:
            if x is None:
                return None
            return round(float(x), n)
        except Exception:
            return None

    return {
        "moisture":   r(g("moisture"), 1),
        "tempC":      r(g("temperature_c"), 1),
        "humidity":   r(g("humidity_pct"), 1),
        "light_lux":  r(g("light_lux"), 0),
        "color_index": r(g("color_index"), 2) if g("color_index") is not None else None,
        "ec":          r(g("ec_mScm"), 2) if g("ec_mScm") is not None else None,
        "ph":          r(g("ph"), 2) if g("ph") is not None else None,
        "soil_tempC":  r(g("soil_temp_c"), 1) if g("soil_temp_c") is not None else None,
        "growth_stage": g("growth_stage", "unknown"),
    }

def compact_string(fv: dict) -> str:
    def fmt(v): return "NA" if v is None else v
    return (
        f"moisture={fmt(fv['moisture'])}%, "
        f"tempC={fmt(fv['tempC'])}, "
        f"humidity={fmt(fv['humidity'])}%, "
        f"light_lux={fmt(fv['light_lux'])}, "
        f"color_index={fmt(fv['color_index'])}, "
        f"ec={fmt(fv.get('ec'))}, ph={fmt(fv.get('ph'))}, "
        f"soil_tempC={fmt(fv.get('soil_tempC'))}, "
        f"growth_stage={fmt(fv['growth_stage'])}"
    )

def json_safe(obj):
    """Ensure no NaN/Inf in JSON (return None instead)."""
    if isinstance(obj, dict):
        return {k: json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [json_safe(v) for v in obj]
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
    return obj

def fetch_latest(uid: str) -> Optional[dict]:
    init_rtdb()
    latest = db.reference(f"/nodes/{uid}/latest").get()
    if isinstance(latest, dict) and latest:
        return normalize_latest(latest)
    # fallback to newest from history
    hist = db.reference(f"/nodes/{uid}/history").get() or {}
    if isinstance(hist, dict) and hist:
        newest = max(hist.values(), key=lambda x: x.get("ts", 0))
        return normalize_latest(newest)
    return None

# ---------- LLM Prompt ----------
TEMPLATE = """
You are an expert cultivation AI assistant specializing in plant growth optimization.
Use the given readings to produce:
1) Diagnosis (short).
2) Next Steps (numbered, specific, measurable).
Readings:
{plant_data}
User question:
{user_question}
"""

class AskIn(BaseModel):
    uid: str
    user_question: str

# ---------- Routes ----------
@app.get("/health")
def health():
    return {"ok": True}

@app.get("/latest")
def latest(uid: str = Query(...)):
    pkt = fetch_latest(uid)
    if not pkt:
        return {"error": "no_data"}
    fv = feature_vector(pkt)
    return {"features": json_safe(fv), "compact": compact_string(fv)}

@app.post("/ask")
def ask(body: AskIn):
    pkt = fetch_latest(body.uid)
    if not pkt:
        return {"error": "no_data"}
    fv = feature_vector(pkt)
    plant_data = compact_string(fv)
    model = OllamaLLM(model=OLLAMA_MODEL)
    chain = ChatPromptTemplate.from_template(TEMPLATE) | model
    out = chain.invoke({"plant_data": plant_data, "user_question": body.user_question})
    return {"answer": out, "readings": json_safe(fv)}

# Optional: run directly
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)

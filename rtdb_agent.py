# rtdb_agent.py
# ------------------------------------------------------------
# RTDB -> (latest + history) -> normalize -> stats/trend -> LLM
# Run:
#   1) ollama serve
#   2) python rtdb_agent.py --uid <UID> --cred "C:\path\service_account.json" --hist 60 --q "Should I water now?"
# ------------------------------------------------------------

import os, math, argparse, statistics
from typing import List, Dict, Any, Optional, Tuple

import firebase_admin
from firebase_admin import credentials, db
from langchain_ollama.llms import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate

DEFAULT_RTDB_URL = "https://giatest-74d4a-default-rtdb.firebaseio.com"

# ---------- Firebase init ----------
def init_rtdb(database_url: str, cred_path: str):
    if not firebase_admin._apps:
        if cred_path and os.path.exists(cred_path):
            print(f"🔐 Using explicit credential file: {cred_path}")
            cred = credentials.Certificate(cred_path)
        else:
            print("⚠️ No credential file provided or not found; using default application credentials.")
            cred = credentials.ApplicationDefault()
        firebase_admin.initialize_app(cred, {"databaseURL": database_url})
        print("✅ Firebase initialized.")

# ---------- Conversions / Normalization ----------
def f_to_c(val_f):
    try:
        return (float(val_f) - 32.0) * (5.0 / 9.0) if val_f is not None else None
    except Exception:
        return None

def normalize_rtdb_sample(raw: dict) -> dict:
    # raw fields: hum (RH%), temp (°F), soil (%), light (lux), ts (epoch-ish seconds)
    return {
        "ts": raw.get("ts"),
        "moisture": raw.get("soil"),
        "temperature_c": f_to_c(raw.get("temp")),
        "humidity_pct": raw.get("hum"),
        "light_lux": raw.get("light"),
    }

def normalize_latest(raw_latest: dict) -> dict:
    # Same mapping but without timestamp enforcement
    return {
        "moisture": raw_latest.get("soil"),
        "temperature_c": f_to_c(raw_latest.get("temp")),
        "humidity_pct": raw_latest.get("hum"),
        "light_lux": raw_latest.get("light"),
        "color_index": None,
        "ec_mScm": None,
        "ph": None,
        "soil_temp_c": None,
        "growth_stage": "unknown",
    }

# ---------- Fetch ----------
def fetch_latest(uid: str) -> Optional[dict]:
    latest_ref = db.reference(f"/nodes/{uid}/latest")
    latest = latest_ref.get()
    if isinstance(latest, dict) and latest:
        print("📥 Fetched latest data node.")
        return normalize_latest(latest)
    return None

def fetch_history(uid: str) -> List[dict]:
    hist_ref = db.reference(f"/nodes/{uid}/history")
    snap = hist_ref.get() or {}
    if not isinstance(snap, dict) or not snap:
        return []
    # snap is a dict of pushId -> sample
    samples = []
    for v in snap.values():
        if isinstance(v, dict):
            n = normalize_rtdb_sample(v)
            if n.get("ts") is not None:
                samples.append(n)
    # sort by ts ascending
    samples.sort(key=lambda x: x["ts"])
    return samples

# ---------- Basic stats / trend ----------
def _safe_series(samples: List[dict], key: str) -> List[Tuple[float, float]]:
    """Return list of (t, value) for samples where value is not None."""
    out = []
    for s in samples:
        t = s.get("ts")
        v = s.get(key)
        if t is None or v is None:
            continue
        try:
            out.append((float(t), float(v)))
        except Exception:
            pass
    return out

def _slope_per_hour(series: List[Tuple[float, float]]) -> Optional[float]:
    """Approximate slope as (last - first) / hours_between."""
    if len(series) < 2:
        return None
    t0, v0 = series[0]
    t1, v1 = series[-1]
    dt = max(1e-6, t1 - t0)
    hours = dt / 3600.0
    if hours <= 0:
        return None
    return (v1 - v0) / hours

def _min_max_avg(values: List[float]) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    if not values:
        return None, None, None
    return min(values), max(values), statistics.fmean(values)

def describe_history(samples: List[dict], latest: dict, limit: int) -> str:
    """Build a compact history summary for the prompt."""
    if not samples:
        return "no_history"

    # Limit to last N items by time
    recent = samples[-limit:] if limit > 0 else samples
    if len(recent) < 2:
        return "insufficient_points"

    t0, t1 = recent[0]["ts"], recent[-1]["ts"]
    window_hr = max(0.0, (t1 - t0) / 3600.0)

    # Build series
    m_series = _safe_series(recent, "moisture")
    t_series = _safe_series(recent, "temperature_c")
    h_series = _safe_series(recent, "humidity_pct")
    l_series = _safe_series(recent, "light_lux")

    # Stats
    m_vals = [v for _, v in m_series]
    t_vals = [v for _, v in t_series]
    h_vals = [v for _, v in h_series]
    l_vals = [v for _, v in l_series]

    m_min, m_max, m_avg = _min_max_avg(m_vals)
    t_min, t_max, t_avg = _min_max_avg(t_vals)
    h_min, h_max, h_avg = _min_max_avg(h_vals)
    l_min, l_max, l_avg = _min_max_avg(l_vals)

    m_slope = _slope_per_hour(m_series)  # % per hour
    t_slope = _slope_per_hour(t_series)  # °C per hour
    h_slope = _slope_per_hour(h_series)  # %RH per hour
    l_slope = _slope_per_hour(l_series)  # lux per hour

    def fmt(x, n=1):
        return "NA" if x is None else (f"{x:.{n}f}")

    summary = (
        f"window={fmt(window_hr,1)}h; "
        f"moisture avg {fmt(m_avg)}% (min {fmt(m_min)} max {fmt(m_max)}), trend {fmt(m_slope)}%/h; "
        f"tempC avg {fmt(t_avg)} (min {fmt(t_min)} max {fmt(t_max)}), trend {fmt(t_slope)}°C/h; "
        f"humidity avg {fmt(h_avg)}% (min {fmt(h_min)} max {fmt(h_max)}), trend {fmt(h_slope)}%/h; "
        f"light avg {fmt(l_avg,0)} lux (min {fmt(l_min,0)} max {fmt(l_max,0)}), trend {fmt(l_slope,0)} lux/h."
    )
    return summary

# ---------- Feature vector & compact string ----------
def feature_vector(d: dict) -> dict:
    def g(k, default=None): return d.get(k, default)
    def r(x, n):
        try:
            if x is None: return float("nan")
            return round(float(x), n)
        except Exception:
            return float("nan")
    return {
        "moisture": r(g("moisture"), 1),
        "tempC": r(g("temperature_c"), 1),
        "humidity": r(g("humidity_pct"), 1),
        "light_lux": r(g("light_lux"), 0),
        "color_index": r(g("color_index"), 2) if g("color_index") is not None else float("nan"),
        "ec": r(g("ec_mScm"), 2) if g("ec_mScm") is not None else "NA",
        "ph": r(g("ph"), 2) if g("ph") is not None else "NA",
        "soil_tempC": r(g("soil_temp_c"), 1) if g("soil_temp_c") is not None else "NA",
        "growth_stage": g("growth_stage", "unknown"),
    }

def compact_string(fv: dict) -> str:
    def fmt(v):
        if isinstance(v, (int, float)) and math.isnan(v): return "NA"
        return v
    return (
        f"moisture={fmt(fv['moisture'])}%, "
        f"tempC={fmt(fv['tempC'])}, "
        f"humidity={fmt(fv['humidity'])}%, "
        f"light_lux={fmt(fv['light_lux'])}, "
        f"color_index={fmt(fv['color_index'])}, "
        f"ec={fmt(fv.get('ec','NA'))}, ph={fmt(fv.get('ph','NA'))}, "
        f"soil_tempC={fmt(fv.get('soil_tempC','NA'))}, "
        f"growth_stage={fmt(fv['growth_stage'])}"
    )

# ---------- Prompt ----------
TEMPLATE = """
You are an expert cultivation AI assistant specializing in plant growth optimization and gives the user actionable advice they dont need to spend money for.

Inputs:
- Latest readings (snapshot): {plant_data}
- Recent history summary: {history_summary}

Goal:
- Provide actionable advice based on both the latest snapshot and recent trends.
- Interpret the snapshot in the context of the trend. If the trend contradicts the snapshot (e.g., moisture rising fast), adjust your recommendations accordingly.

Rules:
- Be elaborate but concise.
- First compare trend vs snapshot in one sentence.
- Output:

1. Diagnosis:
   - What the latest + trend indicate (e.g., “Moisture is low and still falling ~4%/h.”)
2. Next Steps:
   1. Specific, measurable actions (e.g., “Add 150–200 ml water to reach ~50%.”)
   2. Why each action helps.
   3. Timing/checks (e.g., “recheck in 2h”; “shade at noon”).

If history is insufficient, say “limited history; acting on snapshot.”
User question:
{user_question}
"""

# ---------- Main ----------
def main():
    parser = argparse.ArgumentParser(description="RTDB → (latest + history) → Ollama cultivation agent")
    parser.add_argument("--uid", required=True, help="Your node/user UID under /nodes/<UID>")
    parser.add_argument("--cred", required=True, help="Full path to Firebase service_account.json")
    parser.add_argument("--hist", type=int, default=48, help="How many recent history points to consider (default 48)")
    parser.add_argument("--dburl", default=DEFAULT_RTDB_URL, help="Firebase RTDB URL")
    parser.add_argument("--q", "--question", dest="question",
                        default="What should I do next based on these readings and trends?",
                        help="User question to ground the advice")
    args = parser.parse_args()

    # Init
    init_rtdb(args.dburl, args.cred)

    # Fetch latest + history
    latest_raw = fetch_latest(args.uid)
    history_raw = fetch_history(args.uid)

    if not latest_raw and not history_raw:
        print("❌ No RTDB data found. Check /nodes/<UID>/latest or /history.")
        return

    # If no latest, synthesize from last history point
    if not latest_raw and history_raw:
        last_hist = history_raw[-1]
        latest_raw = {
            "moisture": last_hist.get("moisture"),
            "temperature_c": last_hist.get("temperature_c"),
            "humidity_pct": last_hist.get("humidity_pct"),
            "light_lux": last_hist.get("light_lux"),
            "color_index": None, "ec_mScm": None, "ph": None, "soil_temp_c": None,
            "growth_stage": "unknown"
        }

    fv = feature_vector(latest_raw)
    plant_data = compact_string(fv)
    history_summary = describe_history(history_raw, latest_raw, args.hist)

    # LLM
    model = OllamaLLM(model="llama3.2")
    chain = ChatPromptTemplate.from_template(TEMPLATE) | model

    out = chain.invoke({
        "plant_data": plant_data,
        "history_summary": history_summary,
        "user_question": args.question
    })

    print("\n📦 Snapshot:", plant_data)
    print("🕘 History:", history_summary)
    print("\n🧠 Advice:\n" + out)

if __name__ == "__main__":
    main()
# rtdb_agent.py
# ------------------------------------------------------------
# RTDB -> (latest + history) -> normalize -> stats/trend -> LLM
# Run:
#   1) ollama serve
#   2) python rtdb_agent.py --uid <UID> --cred "C:\path\service_account.json" --hist 60 --q "Should I water now?"
# ------------------------------------------------------------

import os, math, argparse, statistics
from typing import List, Dict, Any, Optional, Tuple

import firebase_admin
from firebase_admin import credentials, db
from langchain_ollama.llms import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate

DEFAULT_RTDB_URL = "https://giatest-74d4a-default-rtdb.firebaseio.com"

# ---------- Firebase init ----------
def init_rtdb(database_url: str, cred_path: str):
    if not firebase_admin._apps:
        if cred_path and os.path.exists(cred_path):
            print(f"🔐 Using explicit credential file: {cred_path}")
            cred = credentials.Certificate(cred_path)
        else:
            print("⚠️ No credential file provided or not found; using default application credentials.")
            cred = credentials.ApplicationDefault()
        firebase_admin.initialize_app(cred, {"databaseURL": database_url})
        print("✅ Firebase initialized.")

# ---------- Conversions / Normalization ----------
def f_to_c(val_f):
    try:
        return (float(val_f) - 32.0) * (5.0 / 9.0) if val_f is not None else None
    except Exception:
        return None

def normalize_rtdb_sample(raw: dict) -> dict:
    # raw fields: hum (RH%), temp (°F), soil (%), light (lux), ts (epoch-ish seconds)
    return {
        "ts": raw.get("ts"),
        "moisture": raw.get("soil"),
        "temperature_c": f_to_c(raw.get("temp")),
        "humidity_pct": raw.get("hum"),
        "light_lux": raw.get("light"),
    }

def normalize_latest(raw_latest: dict) -> dict:
    # Same mapping but without timestamp enforcement
    return {
        "moisture": raw_latest.get("soil"),
        "temperature_c": f_to_c(raw_latest.get("temp")),
        "humidity_pct": raw_latest.get("hum"),
        "light_lux": raw_latest.get("light"),
        "color_index": None,
        "ec_mScm": None,
        "ph": None,
        "soil_temp_c": None,
        "growth_stage": "unknown",
    }

# ---------- Fetch ----------
def fetch_latest(uid: str) -> Optional[dict]:
    latest_ref = db.reference(f"/nodes/{uid}/latest")
    latest = latest_ref.get()
    if isinstance(latest, dict) and latest:
        print("📥 Fetched latest data node.")
        return normalize_latest(latest)
    return None

def fetch_history(uid: str) -> List[dict]:
    hist_ref = db.reference(f"/nodes/{uid}/history")
    snap = hist_ref.get() or {}
    if not isinstance(snap, dict) or not snap:
        return []
    # snap is a dict of pushId -> sample
    samples = []
    for v in snap.values():
        if isinstance(v, dict):
            n = normalize_rtdb_sample(v)
            if n.get("ts") is not None:
                samples.append(n)
    # sort by ts ascending
    samples.sort(key=lambda x: x["ts"])
    return samples

# ---------- Basic stats / trend ----------
def _safe_series(samples: List[dict], key: str) -> List[Tuple[float, float]]:
    """Return list of (t, value) for samples where value is not None."""
    out = []
    for s in samples:
        t = s.get("ts")
        v = s.get(key)
        if t is None or v is None:
            continue
        try:
            out.append((float(t), float(v)))
        except Exception:
            pass
    return out

def _slope_per_hour(series: List[Tuple[float, float]]) -> Optional[float]:
    """Approximate slope as (last - first) / hours_between."""
    if len(series) < 2:
        return None
    t0, v0 = series[0]
    t1, v1 = series[-1]
    dt = max(1e-6, t1 - t0)
    hours = dt / 3600.0
    if hours <= 0:
        return None
    return (v1 - v0) / hours

def _min_max_avg(values: List[float]) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    if not values:
        return None, None, None
    return min(values), max(values), statistics.fmean(values)

def describe_history(samples: List[dict], latest: dict, limit: int) -> str:
    """Build a compact history summary for the prompt."""
    if not samples:
        return "no_history"

    # Limit to last N items by time
    recent = samples[-limit:] if limit > 0 else samples
    if len(recent) < 2:
        return "insufficient_points"

    t0, t1 = recent[0]["ts"], recent[-1]["ts"]
    window_hr = max(0.0, (t1 - t0) / 3600.0)

    # Build series
    m_series = _safe_series(recent, "moisture")
    t_series = _safe_series(recent, "temperature_c")
    h_series = _safe_series(recent, "humidity_pct")
    l_series = _safe_series(recent, "light_lux")

    # Stats
    m_vals = [v for _, v in m_series]
    t_vals = [v for _, v in t_series]
    h_vals = [v for _, v in h_series]
    l_vals = [v for _, v in l_series]

    m_min, m_max, m_avg = _min_max_avg(m_vals)
    t_min, t_max, t_avg = _min_max_avg(t_vals)
    h_min, h_max, h_avg = _min_max_avg(h_vals)
    l_min, l_max, l_avg = _min_max_avg(l_vals)

    m_slope = _slope_per_hour(m_series)  # % per hour
    t_slope = _slope_per_hour(t_series)  # °C per hour
    h_slope = _slope_per_hour(h_series)  # %RH per hour
    l_slope = _slope_per_hour(l_series)  # lux per hour

    def fmt(x, n=1):
        return "NA" if x is None else (f"{x:.{n}f}")

    summary = (
        f"window={fmt(window_hr,1)}h; "
        f"moisture avg {fmt(m_avg)}% (min {fmt(m_min)} max {fmt(m_max)}), trend {fmt(m_slope)}%/h; "
        f"tempC avg {fmt(t_avg)} (min {fmt(t_min)} max {fmt(t_max)}), trend {fmt(t_slope)}°C/h; "
        f"humidity avg {fmt(h_avg)}% (min {fmt(h_min)} max {fmt(h_max)}), trend {fmt(h_slope)}%/h; "
        f"light avg {fmt(l_avg,0)} lux (min {fmt(l_min,0)} max {fmt(l_max,0)}), trend {fmt(l_slope,0)} lux/h."
    )
    return summary

# ---------- Feature vector & compact string ----------
def feature_vector(d: dict) -> dict:
    def g(k, default=None): return d.get(k, default)
    def r(x, n):
        try:
            if x is None: return float("nan")
            return round(float(x), n)
        except Exception:
            return float("nan")
    return {
        "moisture": r(g("moisture"), 1),
        "tempC": r(g("temperature_c"), 1),
        "humidity": r(g("humidity_pct"), 1),
        "light_lux": r(g("light_lux"), 0),
        "color_index": r(g("color_index"), 2) if g("color_index") is not None else float("nan"),
        "ec": r(g("ec_mScm"), 2) if g("ec_mScm") is not None else "NA",
        "ph": r(g("ph"), 2) if g("ph") is not None else "NA",
        "soil_tempC": r(g("soil_temp_c"), 1) if g("soil_temp_c") is not None else "NA",
        "growth_stage": g("growth_stage", "unknown"),
    }

def compact_string(fv: dict) -> str:
    def fmt(v):
        if isinstance(v, (int, float)) and math.isnan(v): return "NA"
        return v
    return (
        f"moisture={fmt(fv['moisture'])}%, "
        f"tempC={fmt(fv['tempC'])}, "
        f"humidity={fmt(fv['humidity'])}%, "
        f"light_lux={fmt(fv['light_lux'])}, "
        f"color_index={fmt(fv['color_index'])}, "
        f"ec={fmt(fv.get('ec','NA'))}, ph={fmt(fv.get('ph','NA'))}, "
        f"soil_tempC={fmt(fv.get('soil_tempC','NA'))}, "
        f"growth_stage={fmt(fv['growth_stage'])}"
    )

# ---------- Prompt ----------
TEMPLATE = """
You are an expert cultivation AI assistant specializing in plant growth optimization and gives the user actionable advice they dont need to spend money for.

Inputs:
- Latest readings (snapshot): {plant_data}
- Recent history summary: {history_summary}

Goal:
- Provide actionable advice based on both the latest snapshot and recent trends.
- Interpret the snapshot in the context of the trend. If the trend contradicts the snapshot (e.g., moisture rising fast), adjust your recommendations accordingly.

Rules:
- Be elaborate but concise.
- First compare trend vs snapshot in one sentence.
- Output:

1. Diagnosis:
   - What the latest + trend indicate (e.g., “Moisture is low and still falling ~4%/h.”)
2. Next Steps:
   1. Specific, measurable actions (e.g., “Add 150–200 ml water to reach ~50%.”)
   2. Why each action helps.
   3. Timing/checks (e.g., “recheck in 2h”; “shade at noon”).

If history is insufficient, say “limited history; acting on snapshot.”
User question:
{user_question}
"""

# ---------- Main ----------
def main():
    parser = argparse.ArgumentParser(description="RTDB → (latest + history) → Ollama cultivation agent")
    parser.add_argument("--uid", required=True, help="Your node/user UID under /nodes/<UID>")
    parser.add_argument("--cred", required=True, help="Full path to Firebase service_account.json")
    parser.add_argument("--hist", type=int, default=48, help="How many recent history points to consider (default 48)")
    parser.add_argument("--dburl", default=DEFAULT_RTDB_URL, help="Firebase RTDB URL")
    parser.add_argument("--q", "--question", dest="question",
                        default="What should I do next based on these readings and trends?",
                        help="User question to ground the advice")
    args = parser.parse_args()

    # Init
    init_rtdb(args.dburl, args.cred)

    # Fetch latest + history
    latest_raw = fetch_latest(args.uid)
    history_raw = fetch_history(args.uid)

    if not latest_raw and not history_raw:
        print("❌ No RTDB data found. Check /nodes/<UID>/latest or /history.")
        return

    # If no latest, synthesize from last history point
    if not latest_raw and history_raw:
        last_hist = history_raw[-1]
        latest_raw = {
            "moisture": last_hist.get("moisture"),
            "temperature_c": last_hist.get("temperature_c"),
            "humidity_pct": last_hist.get("humidity_pct"),
            "light_lux": last_hist.get("light_lux"),
            "color_index": None, "ec_mScm": None, "ph": None, "soil_temp_c": None,
            "growth_stage": "unknown"
        }

    fv = feature_vector(latest_raw)
    plant_data = compact_string(fv)
    history_summary = describe_history(history_raw, latest_raw, args.hist)

    # LLM
    model = OllamaLLM(model="llama3.2")
    chain = ChatPromptTemplate.from_template(TEMPLATE) | model

    out = chain.invoke({
        "plant_data": plant_data,
        "history_summary": history_summary,
        "user_question": args.question
    })

    print("\n📦 Snapshot:", plant_data)
    print("🕘 History:", history_summary)
    print("\n🧠 Advice:\n" + out)

if __name__ == "__main__":
    main()

import math
from langchain_ollama.llms import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate

# --- Replace this with your Firebase fetch ---
# Example raw JSON record coming from Firebase
raw = {
    "moisture": 41.2,
    "temperature_c": 25.3,
    "humidity_pct": 58.1,
    "light_lux": 9200,
    "ec_mScm": 2.1,          # optional
    "ph": 6.4,               # optional
    "soil_temp_c": 23.8,     # optional
    "color_index": 0.62,     # from image classifier
    "growth_stage": "veg"    # "seedling" | "veg" | "flower"
}

# --- Minimal featurizer: select + round + default fallbacks ---
def feature_vector(d: dict) -> dict:
    def g(key, default=None): return d.get(key, default)
    return {
        "moisture": round(g("moisture", float("nan")), 1),
        "tempC": round(g("temperature_c", float("nan")), 1),
        "humidity": round(g("humidity_pct", float("nan")), 1),
        "light_lux": round(g("light_lux", float("nan"))),
        "color_index": round(g("color_index", float("nan")), 2),
        "ec": round(g("ec_mScm", float("nan")), 2) if g("ec_mScm") is not None else "NA",
        "ph": round(g("ph", float("nan")), 2) if g("ph") is not None else "NA",
        "soil_tempC": round(g("soil_temp_c", float("nan")), 1) if g("soil_temp_c") is not None else "NA",
        "growth_stage": g("growth_stage", "unknown")
    }

def compact_string(fv: dict) -> str:
    def fmt(v):
        if isinstance(v, (int, float)):
            if math.isnan(v): return "NA"
        return v
    return (
        f"moisture={fmt(fv['moisture'])}%, "
        f"tempC={fmt(fv['tempC'])}, "
        f"humidity={fmt(fv['humidity'])}%, "
        f"light_lux={fmt(fv['light_lux'])}, "
        f"color_index={fmt(fv['color_index'])}, "
        f"ec={fmt(fv['ec'])}, ph={fmt(fv['ph'])}, "
        f"soil_tempC={fmt(fv['soil_tempC'])}, "
        f"growth_stage={fv['growth_stage']}"
    )

fv = feature_vector(raw)
plant_data_str = compact_string(fv)

# --- Your LLM chain (unchanged) ---
model = OllamaLLM(model="llama3.2")

template = """
You are an expert cultivation AI assistant specializing in plant growth optimization.

Input: numeric sensor and image data (moisture, temperature, humidity, light_intensity, color_index, growth_stage).

Your goal: interpret these values, identify what they mean for the plant’s current health,
and give specific, cause-and-effect actions that help the user understand *why* each step matters.

Rules:
- Be direct and concise (under 100 words total).
- Use the data to explain briefly what’s good or off.
- Always structure the output like this:

1. Diagnosis:
   - Summarize what the data indicates (e.g., “Moisture is below ideal range—plant may be under-watered.”)
2. Next Steps:
   1. Give specific, measurable actions (e.g., “Add 150–200ml of water to raise soil moisture to 50%.”)
   2. Mention how the action helps the plant recover or thrive.
   3. Include any notes on adjusting environment (light, airflow, temperature).

Example tone:
"Temperature is stable, but moisture is dropping below the healthy range.
Add water soon to prevent stress and leaf curl."

Here are the plant readings:
{plant_data}

User question:
{user_question}
"""
prompt = ChatPromptTemplate.from_template(template)
chain = prompt | model

result = chain.invoke({
    "plant_data": plant_data_str,
    "user_question": "Given what you know about the plant's current readings, what should I do next to ensure I can keep my basil alive?"
})
print(result)

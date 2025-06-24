# 🌿 Gianode

**Gianode** is a modular, AI-enhanced plant care system. It combines vision, sensors, and GPT logic to monitor, learn from, and care for your plants — indoor or outdoor.

Built for growers, students, and researchers, Gianode makes intelligent plant care affordable, explainable, and personal.

---

## 💡 What Is It?

**Gia** is the plant assistant.  
**Gianode** is the physical system — ESP32-CAM + soil sensors + logic.  
Together they:
- Capture visual + soil data
- Analyze health using OpenCV or Teachable Machine
- Log environmental conditions
- Generate care suggestions using GPT
- Optionally automate lighting, watering, or alerts

---

## 🧰 Features

- 📷 ESP32-CAM image capture
- 🌱 Soil moisture, temp, and pH sensors
- 🧠 Image classification (droopy, yellowing, healthy)
- 🧬 GPT-based daily plant analysis (JSON → response)
- 🔌 Smart plug support for automation
- 📡 Optional Firebase or MQTT integration

---
# 🌿 Gianode

**Gianode** is an open, modular AI-based plant care system.  
It’s split into two parts:

- **Gia** – the intelligent assistant (classification, GPT, care suggestions)  
- **Node** – the physical system (camera + soil/environment sensors)

Together, they form a low-cost, expandable platform for indoor and outdoor plant monitoring, automation, and education.

---

## 🗂️ Repo Structure
<pre>
gianode/
├── Gia/                   # AI + learning engine
│   ├── classify_image.py
│   ├── analyze_data.py
│   ├── gpt_response.py
│   ├── training/
│   │   ├── dataset/
│   │   └── notes.md
│   └── utils/
│       └── __init__.py
│
├── Node/                  # Hardware & sensor-side logic
│   ├── read_sensors.py
│   ├── capture_image.py
│   ├── control_plug.py
│   ├── build_json.py
│   └── config/
│       └── node_config.json
│
├── pipeline/              # Master controller scripts
│   ├── run_pipeline.py
│   └── cronjob.sh
│
├── data/                  # Logs + image capture
│   ├── images/
│   └── logs/
│
├── dashboard/             # (Optional) Local Flask UI
│   └── app.py
│
├── docs/                  # Diagrams, notes, and planning
│   └── architecture.png
│
├── index.html             # GitHub Pages homepage
├── CNAME                  # Domain reference
├── README.md
├── requirements.txt       # Dependencies
└── LICENSE
</pre>
---

## 🔁 How It Works

1. `Node` collects sensor data and a plant image
2. Data is combined into a JSON payload
3. `Gia` classifies the image and interprets the environment
4. A care recommendation or action is returned
5. Optional smart plug or alert is triggered

---
## 🛠 Getting Started

```bash
git clone https://github.com/YOURUSERNAME/gianode.git
cd gianode
pip install -r requirements.txt
python3 pipeline/run_pipeline.py
{
  "timestamp": "2025-06-24 08:00",
  "class": "droopy",
  "moisture": 41,
  "pH": 6.3,
  "temp": 24.5,
  "growth_stage": "veg"
}
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

## 🧠 Architecture Overview
        +--------------------+
        |       Gia          |
        |  (AI + GPT Brain)  |
        +---------+----------+
                  ^
                  |
     JSON         |           +--------------------+
(image + sensor)  +-----------+       Node         |
                              |  (Camera + Sensors)|
                              +--------------------+

## 🗂️ Repo Structure
gianode/
├── Gia/               # AI + learning engine
│   ├── classify_image.py
│   ├── analyze_data.py
│   └── gpt_response.py
│
├── Node/              # Sensor + camera data collection
│   ├── read_sensors.py
│   ├── capture_image.py
│   └── control_plug.py
│
├── pipeline/          # Orchestrates full cycle
│   └── run_pipeline.py
│
├── data/              # Example logs + images
├── dashboard/         # Optional local interface
├── docs/              # Diagrams, architecture
├── README.md
├── requirements.txt
└── index.html         # GitHub Pages homepage